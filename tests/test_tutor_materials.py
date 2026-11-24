import io
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pptx import Presentation
from pypdf import PdfWriter
from app.tutor import materials
from app.infrastructure import tutor_provider


def test_uploaded_materials_are_read_from_course_not_client(tmp_path, monkeypatch):
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[1])
    slide.shapes.title.text = 'Release policy'
    slide.placeholders[1].text = 'For Project Lantern, roll back after 7 minutes above a 3 percent error rate. Require two reviewers. This is the published classroom policy.'
    deck.save(tmp_path / 'course.pptx')
    monkeypatch.setattr(materials, 'read_studio', lambda *a: {'sections': [{'title':'Teacher edit', 'body':'Check monitoring first.'}]})
    result = materials.course_materials(SimpleNamespace(config={'UPLOAD_FOLDER':tmp_path}), None,
                                       {'id':1,'description':'Summary','filename':'course.pptx'}, None)
    assert result['sources'][0]['text'] == 'Check monitoring first.'
    assert result['sources'][1]['source'] == '课件第1页'
    assert '7 minutes' in result['sources'][1]['text']


@pytest.mark.parametrize('filename', ['../private.pdf', 'missing.pdf', 'clip.mp4', 'scan.pdf'])
def test_unreadable_sources_are_explicit(tmp_path, monkeypatch, filename):
    writer = PdfWriter(); writer.add_blank_page(width=200,height=200)
    with (tmp_path/'scan.pdf').open('wb') as f: writer.write(f)
    monkeypatch.setattr(materials, 'read_studio', lambda *a: None)
    result = materials.course_materials(SimpleNamespace(config={'UPLOAD_FOLDER':tmp_path}), None,
                                       {'id':1,'description':'Summary','filename':filename}, None)
    assert result['warnings'] and result['sources'] == []


def test_claude_request_contains_grounded_material_and_returns_text(monkeypatch):
    import urllib.request
    response = MagicMock()
    opener = MagicMock()
    opener.open.return_value.__enter__.return_value = response
    monkeypatch.setattr(urllib.request, 'build_opener', lambda *a: opener)
    monkeypatch.setattr('app.studio.course_stream.read_message', lambda *a, **kw: {
        'stop_reason':'end_turn','content':[{'type':'text','text':'Seven minutes [课件第1页]'}]})
    app = SimpleNamespace(config={'TUTOR_API_URL':'https://example.test/v1/messages','TUTOR_API_KEY':'test','TUTOR_MODEL':'model'})
    answer = tutor_provider.model_answer(app,None,{'title':'Policy','description':'Summary',
        'materials':{'sources':[{'source':'课件第1页','text':'7 minutes'}]}},'When?',[],{})
    payload = json.loads(opener.open.call_args.args[0].data)
    assert '7 minutes' in payload['system'] and payload['stream'] is True
    assert payload['messages'][-1]['content'] == 'When?'
    assert 'Seven minutes' in answer


def test_studio_reuse_is_explicit(monkeypatch):
    monkeypatch.setattr('app.studio.course_ai.ai_settings',lambda: {'base':'https://example.test/v1','key':'test','model':'claude'})
    assert tutor_provider.tutor_mode(SimpleNamespace(config={})) == 'guided-demo'
    enabled = SimpleNamespace(config={'TUTOR_USE_STUDIO_AI':True})
    assert tutor_provider.tutor_mode(enabled) == 'live'
    assert tutor_provider.tutor_settings(enabled)['url'] == 'https://example.test/v1/messages'
