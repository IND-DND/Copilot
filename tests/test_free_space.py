import json
from unittest.mock import Mock

from app.config import Settings
from app.engine import Engine
from app.free_space import answer_question, render
from app.providers import LocalModel, QuranSourceAPI
from app.model_output import checked_summary


def engine(knowledge):
    settings = Settings(ollama_enabled=False)
    return Engine(knowledge, QuranSourceAPI(knowledge), LocalModel(settings), settings)


def test_free_gpu_receives_retrieved_evidence_and_returns_checked_explanation(knowledge):
    def generate(messages):
        evidence = json.loads(messages[1]["content"])["evidence"]
        assert evidence[0]["id"] == "quran-2-177"
        return json.dumps({"summary": "Righteousness includes giving to people in need.", "citations": ["quran-2-177"]})
    answer = answer_question(engine(knowledge), generate, "Quran 2:177", "en", "all", True, "")
    assert answer.mode == "model" and answer.model_status == "used"
    assert answer.citations[0].text == knowledge.verse(2, 177, "en").text


def test_missing_or_invalid_reference_does_not_use_gpu(knowledge):
    generate = Mock()
    answer = answer_question(engine(knowledge), generate, "Quran 999:999", "en", "all", True, "")
    assert answer.mode == "no_sources"
    generate.assert_not_called()


def test_source_only_hindi_fatiha_retains_all_verses_and_footnotes(knowledge):
    generate = Mock()
    answer = answer_question(engine(knowledge), generate, "Translate Surah Al-Fatiha into Hindi", "en", "all", False, "")
    assert answer.language == "hi" and len(answer.citations) == 7
    assert answer.model_status == "disabled"
    assert any(s.footnotes for s in answer.citations)
    generate.assert_not_called()


def test_gpu_quota_failure_leaves_verified_sources_available(knowledge):
    def generate(messages):
        raise RuntimeError("GPU quota exceeded")
    answer = answer_question(engine(knowledge), generate, "Quran 2:177", "hi", "all", True, "")
    assert answer.mode == "retrieval" and answer.model_status == "unavailable"
    assert answer.citations and answer.notices


def test_free_model_invented_citation_is_rejected(knowledge):
    answer = answer_question(engine(knowledge), lambda messages: json.dumps({"summary": "Invented", "citations": ["quran-999-999"]}), "Quran 2:177", "en", "all", True, "")
    assert answer.mode == "retrieval" and answer.model_status == "rejected"


def test_html_renderer_escapes_question_model_text_and_source_text(knowledge):
    answer = answer_question(engine(knowledge), lambda m: "", '<script>alert(1)</script> Quran 2:177', "en", "all", False, "")
    answer.response = '<img src=x onerror=alert(1)>'
    page = render(answer, knowledge.manifest["arabic"]["notice"])
    assert '<script>' not in page and '<img' not in page
    assert '&lt;script&gt;' in page and '&lt;img' in page
    assert 'dir="rtl"' in page
    assert 'Tanzil Quran Text' in page and 'Quran 2:177' in page


def test_fenced_json_is_normalized_but_invented_citations_still_fail(knowledge):
    source = [knowledge.verse(2, 177, "hi")]
    body = json.dumps({"summary": "नेकी में ज़रूरतमंदों को धन देना शामिल है।", "citations": ["quran-2-177"]}, ensure_ascii=False)
    assert checked_summary('```json\n' + body + '\n```', "hi", source)[1] == "used"
    assert checked_summary('```json\n' + body.replace('quran-2-177', 'quran-999-999') + '\n```', "hi", source)[1] == "rejected"
    assert checked_summary('Unverified preface\n' + body, "hi", source)[1] == "rejected"
