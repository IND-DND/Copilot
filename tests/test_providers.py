import hashlib
import json
from dataclasses import replace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from app.config import ROOT, Settings
from app.engine import Engine
from app.providers import LocalModel, QuranSourceAPI, SourceUnavailable
from app.schemas import ChatRequest


async def test_live_api_adapter_preserves_source_text_using_mock_transport(knowledge):
    calls = []

    def transport(request):
        calls.append(str(request.url))
        file = "arabic.json" if request.url.path.endswith("uthmani.json") else "hindi.json"
        return httpx.Response(200, content=(ROOT / "data" / file).read_bytes())

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        api = QuranSourceAPI(knowledge, client)
        sources = await api.verses([(112, 1)], "hi")
        again = await api.verses([(112, 2)], "hi")
    assert len(calls) == 2  # repeated lookups use verified data cached in memory
    assert all(url.startswith("https://raw.githubusercontent.com/risan/quran-json/6523a9") for url in calls)
    assert sources[0].text == knowledge.corpora["hi"]["112"][0]["text"]
    assert sources[0].origin == "api"
    assert again[0].id == "quran-112-2"


@pytest.mark.parametrize("status,body", [(403, b"Denied"), (200, b'{"tampered":true}')])
async def test_api_denial_or_tampering_never_becomes_evidence(knowledge, status, body):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(status, content=body))) as client:
        api = QuranSourceAPI(knowledge, client)
        with pytest.raises(SourceUnavailable):
            await api.verses([(2, 177)], "en")
        assert api.cache == {}


async def test_engine_checks_local_knowledge_before_api_fallback(knowledge):
    kb = Mock(wraps=knowledge)
    kb.verse.return_value = None
    remote = knowledge.verse(112, 1, "en").model_copy(update={"origin": "api"})
    api = Mock()
    api.verses = AsyncMock(return_value=[remote])
    engine = Engine(kb, api, LocalModel(Settings(ollama_enabled=False)), Settings(ollama_enabled=False))
    answer = await engine.answer(ChatRequest(question="Quran 112:1"))
    kb.verse.assert_called_once_with(112, 1, "en")
    api.verses.assert_awaited_once_with([(112, 1)], "en")
    assert answer.source_mode == "api"


async def test_local_result_does_not_need_a_network_request(knowledge):
    api = Mock()
    api.verses = AsyncMock(side_effect=AssertionError("Should not request API"))
    answer = await Engine(knowledge, api, LocalModel(Settings(ollama_enabled=False)), Settings(ollama_enabled=False)).answer(ChatRequest(question="Quran 112:1"))
    assert answer.source_mode == "local"
    api.verses.assert_not_awaited()


async def test_disabled_fallback_is_honored(knowledge):
    kb = Mock(wraps=knowledge)
    kb.verse.return_value = None
    api = Mock()
    api.verses = AsyncMock()
    answer = await Engine(kb, api, LocalModel(Settings(ollama_enabled=False)), Settings(ollama_enabled=False)).answer(ChatRequest(question="Quran 112:1", allow_external=False))
    assert answer.mode == "no_sources"
    api.verses.assert_not_awaited()


async def test_failed_fallback_does_not_return_partial_passage(knowledge):
    kb = Mock(wraps=knowledge)
    kb.verse.side_effect = lambda c, v, lang: None if v == 2 else knowledge.verse(c, v, lang)
    api = Mock()
    api.verses = AsyncMock(side_effect=SourceUnavailable("denied"))
    answer = await Engine(kb, api, LocalModel(Settings(ollama_enabled=False)), Settings(ollama_enabled=False)).answer(ChatRequest(question="Quran 112:1-4"))
    assert not answer.citations
    assert "could not be reached" in answer.response


async def model_answer(knowledge, payload, language="en"):
    settings = replace(Settings(ollama_enabled=False), ollama_enabled=True)
    requests = []

    def transport(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": json.dumps(payload)}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        result = await LocalModel(settings, client).summarize("Explain charity", language, [knowledge.verse(2, 177, language)])
    return result, requests


async def test_optional_ollama_receives_evidence_and_system_prompt(knowledge):
    (summary, status), requests = await model_answer(knowledge, {"summary": "Righteousness includes giving to those in need.", "citations": ["quran-2-177"]})
    assert status == "used"
    assert "Righteousness" in summary
    assert requests[0]["stream"] is False
    assert requests[0]["messages"][0]["role"] == "system"
    evidence = json.loads(requests[0]["messages"][1]["content"])["evidence"]
    assert evidence[0]["id"] == "quran-2-177"
    assert requests[0]["format"]["properties"]["citations"]["items"]["enum"] == ["quran-2-177"]


@pytest.mark.parametrize("summary,citations", [
    ("Invented evidence", ["quran-99-999"]),
    ("Quran 99:999 says this", ["quran-2-177"]),
    ("Sahih Muslim 99999 says this", ["quran-2-177"]),
    ("Read https://untrusted.example", ["quran-2-177"]),
    ('The verse says "invented quote"', ["quran-2-177"]),
    ("Uncited claim", []),
    ("A claim", [123]),
])
async def test_model_invented_citations_links_and_quotes_rejected(knowledge, summary, citations):
    (text, status), _ = await model_answer(knowledge, {"summary": summary, "citations": citations})
    assert text is None
    assert status == "rejected"


async def test_hindi_model_response_requires_hindi(knowledge):
    (text, status), _ = await model_answer(knowledge, {"summary": "English answer", "citations": ["quran-2-177"]}, "hi")
    assert text is None
    assert status == "rejected"


async def test_missing_model_falls_back_to_sources(knowledge):
    def transport(request):
        raise httpx.ConnectError("No local model", request=request)

    settings = replace(Settings(ollama_enabled=False), ollama_enabled=True)
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        answer = await Engine(knowledge, QuranSourceAPI(knowledge), LocalModel(settings, client), settings).answer(ChatRequest(question="Quran 2:177"))
    assert answer.mode == "retrieval"
    assert answer.model_status == "unavailable"
    assert answer.citations
    assert answer.notices


async def test_model_destination_cannot_be_set_to_arbitrary_website(knowledge):
    settings = replace(Settings(ollama_enabled=False), ollama_enabled=True, ollama_url="http://untrusted.example")
    text, status = await LocalModel(settings).summarize("charity", "en", [knowledge.verse(2, 177, "en")])
    assert text is None
    assert status == "unavailable"


def test_data_integrity_pins_all_three_corpora(knowledge):
    for filename in ["arabic.json", "english.json", "hindi.json", "chapters.json"]:
        assert hashlib.sha256((ROOT / "data" / filename).read_bytes()).hexdigest() == knowledge.manifest["checksums"][filename]
