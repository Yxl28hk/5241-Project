def test_stream_accumulation_and_failures():
    import io,json
    from time import monotonic
    from unittest.mock import patch
    from urllib.error import URLError
    from http.client import RemoteDisconnected
    from app.studio.course_stream import read_message,StreamError
    from app.studio.course_ai import request_course,CourseAIError

    class Response(io.BytesIO):
        def __init__(self,data,content_type='text/event-stream'):
            super().__init__(data);self.headers={'Content-Type':content_type}

    def sse(events):return ''.join('event: '+e['type']+'\r\ndata: '+json.dumps(e,ensure_ascii=False)+'\r\n\r\n' for e in events).encode()
    fields={'title':'课程 "quoted"','minutes':15,'section_1_body':'line one\n第二行'}
    payload=json.dumps(fields,ensure_ascii=False)
    events=[{'type':'message_start','message':{'content':[],'usage':{'input_tokens':30}}},
            {'type':'ping'},
            {'type':'content_block_start','index':0,'content_block':{'type':'tool_use','name':'submit_course','input':{}}}]
    events += [{'type':'content_block_delta','index':0,'delta':{'type':'input_json_delta','partial_json':payload[i:i+4]}} for i in range(0,len(payload),4)]
    events += [{'type':'content_block_stop','index':0},{'type':'message_delta','delta':{'stop_reason':'tool_use'},'usage':{'output_tokens':50}},{'type':'message_stop'}]
    progress=[]
    result=read_message(Response(sse(events)),progress.append)
    assert result['content'][0]['input']==fields
    assert result['usage']=={'input_tokens':30,'output_tokens':50}
    assert len(progress)==2
    for records,code in [(events[:-1],'incomplete_response'),(events[:3]+[{'type':'error','error':{'type':'overloaded_error'}}],'provider_stream_error')]:
        try:read_message(Response(sse(records)));raise AssertionError('Accepted failed stream')
        except StreamError as error:assert error.code==code
    try:read_message(Response(b''),deadline=monotonic()-1);raise AssertionError('No deadline')
    except StreamError as error:assert error.code=='timeout'
    try:read_message(Response(b':'+b'a'*(2*1024*1024)));raise AssertionError('No size bound')
    except StreamError as error:assert error.code=='response_too_large'
    assert read_message(Response(json.dumps(result).encode(),'application/json'))==result
    for exception,code in [(RemoteDisconnected(),'connection_interrupted'),(TimeoutError(),'timeout'),(URLError('name unavailable'),'connection_error')]:
        with patch('app.studio.course_ai.ai_settings',return_value={'base':'https://example.invalid','key':'test-placeholder','model':'test'}),patch('app.studio.course_ai.build_opener') as opener:
            opener.return_value.open.side_effect=exception
            try:request_course({'pages':[],'warnings':[]},'auto');raise AssertionError('Accepted transport failure')
            except CourseAIError as error:assert error.code==code
    print('PASS: fragmented tool JSON, Unicode, ping, usage, progress, truncation, provider errors, deadlines, size limit, JSON fallback, distinct transport failures. No network calls.')
