"""Bounded Claude Messages SSE accumulation; never return incomplete tool arguments."""
import json
from time import monotonic

class StreamError(Exception):
    def __init__(self,code):self.code=code

def read_message(response,on_progress=None,deadline=None):
    limit=2*1024*1024
    count=0
    def line():
        nonlocal count
        if deadline is not None and monotonic()>deadline:raise StreamError('timeout')
        raw=response.readline(limit-count+1)
        count+=len(raw)
        if count>limit:raise StreamError('response_too_large')
        return raw
    first=line()
    content_type=response.headers.get('Content-Type','').lower()
    if 'text/event-stream' not in content_type and not first.lstrip().startswith((b'event:',b'data:',b':')):
        chunks=[first]
        while chunks[-1]:chunks.append(line())
        return json.loads(b''.join(chunks))
    message=None;blocks={};fragments={};closed=set();data=[];received=False
    if on_progress:on_progress('云渡已建立连接，正在生成课程草稿…')
    def event(payload):
        nonlocal message,received
        item=json.loads(payload)
        kind=item.get('type')
        if kind=='error':raise StreamError('provider_stream_error')
        if kind=='message_start':message=item['message'];message['content']=[]
        elif kind=='content_block_start':
            index=item['index']
            if index in blocks:raise StreamError('invalid_response')
            blocks[index]=item['content_block']
        elif kind=='content_block_delta':
            index=item['index'];delta=item['delta']
            if index not in blocks or index in closed:raise StreamError('invalid_response')
            block=blocks[index]
            if delta['type']=='input_json_delta':fragments.setdefault(index,[]).append(delta['partial_json'])
            elif delta['type']=='text_delta':block['text']=block.get('text','')+delta['text']
            if not received and delta['type'] in {'input_json_delta','text_delta'}:
                received=True
                if on_progress:on_progress('正在接收课程内容，完成后将检查字段和来源页码…')
        elif kind=='content_block_stop':
            index=item['index']
            if index not in blocks or index in closed:raise StreamError('invalid_response')
            if index in fragments:blocks[index]['input']=json.loads(''.join(fragments.pop(index)))
            closed.add(index)
        elif kind=='message_delta':
            if message is None:raise StreamError('invalid_response')
            message.update(item.get('delta',{}))
            message.setdefault('usage',{}).update(item.get('usage',{}))
        elif kind=='message_stop':
            if message is None or not blocks or set(blocks)!=closed:raise StreamError('incomplete_response')
            message['content']=[blocks[i] for i in sorted(blocks)]
            return message
        return None
    raw=first
    while raw:
        text=raw.decode('utf-8').rstrip('\r\n')
        if text.startswith('data:'):data.append(text[5:].lstrip(' '))
        elif not text and data:
            result=event('\n'.join(data));data=[]
            if result is not None:return result
        raw=line()
    if data:
        result=event('\n'.join(data))
        if result is not None:return result
    raise StreamError('incomplete_response')
