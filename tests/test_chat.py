import pytest


def ask(client, question, **options):
    response = client.post("/api/chat", json={"question": question, **options})
    assert response.status_code == 200
    return response.json()


def test_charity_cites_actual_local_verse(client, knowledge):
    result = ask(client, "What does the Quran say about charity?")
    verse = next(s for s in result["citations"] if s["id"] == "quran-2-177")
    assert verse["text"] == knowledge.corpora["en"]["2"][176]["text"]
    assert verse["arabic"] == knowledge.corpora["ar"]["2"][176]["text"]
    assert result["source_mode"] == "local"
    assert result["mode"] == "retrieval"
    assert all(s["kind"] == "quran" for s in result["citations"])


def test_full_fatiha_hindi_preserves_published_translation_and_footnotes(client, knowledge):
    result = ask(client, "Can you translate Surah Al-Fatiha into Hindi?")
    assert result["language"] == "hi"
    assert [s["id"] for s in result["citations"]] == [f"quran-1-{v}" for v in range(1, 8)]
    for actual, expected in zip(result["citations"], knowledge.corpora["hi"]["1"]):
        assert actual["text"] == expected["text"]
        assert actual["footnotes"] == expected.get("footnotes", "")
        assert actual["version"] == "1.1.5"


def test_prayer_hadith_queries_do_not_return_quran_passages(client):
    result = ask(client, "What are the Hadiths about prayer times?")
    assert "muslim-612a" in {s["id"] for s in result["citations"]}
    assert all(s["kind"] == "hadith" for s in result["citations"])
    assert all("not a verbatim" in s["note"] for s in result["citations"])


@pytest.mark.parametrize("question", ["Quran 2:287", "Quran 115:1", "Quran 2:0", "Quran 2:8-3", "Quran 0:1"])
def test_invalid_references_are_not_invented(client, question):
    result = ask(client, question)
    assert result["mode"] == "no_sources"
    assert "invalid" in result["response"]
    assert not result["citations"]


@pytest.mark.parametrize("question", ["Surah 2", "Quran 2:1-21"])
def test_long_passages_are_not_silently_truncated(client, question):
    result = ask(client, question)
    assert result["mode"] == "no_sources"
    assert "20 verses" in result["response"]


def test_multiple_verse_references_retain_order(client):
    result = ask(client, "Quran 112:1-4 and 1:6")
    assert [s["id"] for s in result["citations"]] == ["quran-112-1", "quran-112-2", "quran-112-3", "quran-112-4", "quran-1-6"]


def test_direct_hadith_reference(client):
    result = ask(client, "Sahih Muslim 612")
    assert result["citations"][0]["id"] == "muslim-612a"


def test_unsupported_hadith_does_not_fabricate_a_quote(client):
    result = ask(client, "Sahih al-Bukhari 99999")
    assert result["mode"] == "no_sources"
    assert not result["citations"]


def test_hindi_topic_retrieval(client):
    result = ask(client, "दान के बारे में क़ुरआन क्या कहता है?", language="hi", scope="quran")
    assert result["language"] == "hi"
    assert any(s["id"] == "quran-2-177" for s in result["citations"])
    assert all(s["kind"] == "quran" for s in result["citations"])


def test_response_language_is_separate_from_query_language(client):
    result = ask(client, "What does the Quran say about patience?", language="hi")
    assert result["language"] == "hi"
    assert "धैर्य" in result["citations"][0]["text"] or "सब्र" in result["citations"][0]["text"]


def test_follow_up_translation_uses_previous_question(client):
    result = ask(client, "Translate that into Hindi", context_question="Quran 112:1-4")
    assert result["query"] == "Translate that into Hindi"
    assert result["retrieval_query"] == "Quran 112:1-4"
    assert result["language"] == "hi"
    assert len(result["citations"]) == 4


@pytest.mark.parametrize("question", ["How do I install Python packages?", "Who won the football world cup?", "Is music forbidden?"])
def test_unrelated_or_unsupported_questions_have_no_sources(client, question):
    result = ask(client, question)
    assert result["mode"] == "no_sources"
    assert not result["citations"]


@pytest.mark.parametrize("body", [{"question": " "}, {"question": "x" * 2001}, {"question": "charity", "language": "fr"}, {"question": "charity", "scope": "untrusted"}])
def test_invalid_requests_rejected(client, body):
    assert client.post("/api/chat", json=body).status_code == 422


def test_health_and_source_manifest(client):
    health = client.get("/api/health").json()
    assert health["quran_verses"] == 6236
    assert health["hadith_summaries"] == 5
    source = client.get("/api/sources").json()["quran"]
    assert source["arabic"]["notice"]
    assert {e["lang"] for e in source["translations"]} == {"en", "hi"}


def test_index_and_assets_and_security_headers(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "A little light" in response.text
    assert "script-src 'self'" in response.headers["content-security-policy"]
    for asset in ["app.js", "styles.css", "fonts.css", "favicon.svg"]:
        assert client.get("/static/" + asset).status_code == 200
