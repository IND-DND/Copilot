"""Approved, fixed-origin source API and optional local open-weight model."""

import asyncio
import hashlib
import json
from urllib.parse import urlsplit

import httpx

from .model_output import checked_summary, model_messages
from .schemas import Evidence


class SourceUnavailable(Exception):
    pass


class QuranSourceAPI:
    """The licensed publisher mirror's static JSON API, pinned to a verified revision.

    We do not scrape arbitrary websites. TLS, a fixed host/path, size limits, and
    known SHA-256 digests protect the text. The mirror's upstream terms still apply.
    """

    def __init__(self, knowledge, client=None):
        self.knowledge = knowledge
        self.client = client
        self.cache = {}
        self.lock = asyncio.Lock()

    async def _file(self, name):
        async with self.lock:
            if name in self.cache:
                return self.cache[name]
            manifest = self.knowledge.manifest
            path = manifest["mirror_files"][name]
            url = f"https://raw.githubusercontent.com/risan/quran-json/{manifest['commit']}/{path}"
            owned = self.client is None
            client = self.client or httpx.AsyncClient(timeout=20, follow_redirects=False)
            try:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    chunks = []
                    size = 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > 8_000_000:
                            raise SourceUnavailable("Source response exceeded its size limit.")
                        chunks.append(chunk)
                raw = b"".join(chunks)
                if hashlib.sha256(raw).hexdigest() != manifest["checksums"][name]:
                    raise SourceUnavailable("Source integrity check failed.")
                data = json.loads(raw)
                self.cache[name] = data
                return data
            except (httpx.HTTPError, ValueError, KeyError) as error:
                raise SourceUnavailable("The approved source API is unavailable.") from error
            finally:
                if owned:
                    await client.aclose()

    async def verses(self, references, language):
        arabic = await self._file("arabic.json")
        translated = await self._file("hindi.json" if language == "hi" else "english.json")
        edition = self.knowledge.editions[language]
        result = []
        try:
            for chapter, verse in references:
                if not self.knowledge.valid_reference(chapter, verse):
                    raise SourceUnavailable("Invalid verse reference.")
                entry = translated[str(chapter)][verse - 1]
                ar = arabic[str(chapter)][verse - 1]
                if (entry["chapter"], entry["verse"]) != (chapter, verse) or (ar["chapter"], ar["verse"]) != (chapter, verse):
                    raise SourceUnavailable("Source returned a mismatched reference.")
                result.append(Evidence(
                    id=f"quran-{chapter}-{verse}", reference=f"Quran {chapter}:{verse} · {self.knowledge.chapters[chapter]['transliteration']}",
                    kind="quran", arabic=ar["text"], text=entry["text"], footnotes=entry.get("footnotes", ""),
                    url=f"https://quranenc.com/en/browse/{edition['key']}/{chapter}#{verse}",
                    publisher=edition["title"] + " / QuranEnc.com; Arabic: Tanzil Project", version=edition["version"],
                    license="QuranEnc republication terms; Arabic: CC BY 3.0 (verbatim)",
                    license_url=self.knowledge.manifest["translation_terms"]["url"], origin="api",
                    note=f"Retrieved from the licensed JSON mirror at revision {self.knowledge.manifest['commit'][:12]}; not a live edition update.",
                ))
        except (KeyError, IndexError, TypeError) as error:
            raise SourceUnavailable("Source response is incomplete.") from error
        return result


class LocalModel:
    def __init__(self, settings, client=None):
        self.settings = settings
        self.client = client
        self.slots = asyncio.Semaphore(2)

    async def summarize(self, question, language, evidence):
        if not self.settings.ollama_enabled:
            return None, "disabled"
        url = urlsplit(self.settings.ollama_url)
        if url.scheme not in {"http", "https"} or url.hostname not in {"127.0.0.1", "localhost", "::1"} or url.username or url.password or url.path not in {"", "/"} or url.query or url.fragment:
            return None, "unavailable"
        sources = evidence[:4]
        if not sources:
            return None, "rejected"
        evidence_ids = [s.id for s in sources]
        schema = {"type": "object", "properties": {"summary": {"type": "string"}, "citations": {"type": "array", "items": {"type": "string", "enum": evidence_ids}, "minItems": 1}}, "required": ["summary", "citations"], "additionalProperties": False}
        payload = {
            "model": self.settings.ollama_model, "stream": False, "format": schema,
            "messages": model_messages(question, language, sources),
            "options": {"temperature": 0, "num_predict": 450, "num_ctx": 8192},
        }
        client = self.client or httpx.AsyncClient(timeout=45, trust_env=False)
        try:
            async with self.slots:
                response = await client.post(self.settings.ollama_url + "/api/chat", json=payload)
                response.raise_for_status()
            return checked_summary(response.json()["message"]["content"], language, sources)
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError, AttributeError):
            return None, "unavailable"
        finally:
            if self.client is None:
                await client.aclose()
