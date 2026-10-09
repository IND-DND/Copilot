# Noor · Islamic knowledge chatbot

A runnable, source-grounded chatbot based on the supplied Islamic knowledge assistant prompt. It has a responsive chat interface, English/Hindi language selection, Arabic Quran passages, citations, translator footnotes, and optional server-side Ollama explanations. It works without a paid inference API key.

## Run entirely in the cloud

Visitors need only a browser. The application, text library, and Ollama model run
on the cloud server, with no installation or model files on the visitor's computer.
Chats are held in page memory and cleared on reload; the app uses no browser
storage, cookies, or conversation database. HTTP responses request `no-store`.
The browser still needs to load and display the interface in memory.

The default cloud package targets a **Hugging Face Docker Space**. Hugging Face is
a managed host for this open-source application. For an open-source hosting
control panel on your own cloud server, use **Coolify** with the Docker Compose
deployment below.

`deploy/huggingface/Dockerfile` includes the application and a pinned, CPU-only
Ollama runtime. `deploy/huggingface/README.md` sets the Space's port to 7860. The
model downloads onto the cloud server at startup; source retrieval is available
while it downloads or if it fails. Model files use ephemeral server storage and
may download again after a restart. No persistent volume is required. The
deployment script does not request paid hardware.

From this **cloud workspace**, prepare and publish using a Hugging Face account:

```bash
export UV_CACHE_DIR=/workspace/.cache/uv
uv sync --locked --group deploy
uv run --frozen --group deploy python scripts/deploy_space.py --dry-run
uv run --frozen --group deploy python scripts/deploy_space.py
```

Supply a Hugging Face write token as `NOOR_HF_TOKEN` through secure environment
settings. Do not paste it into chat, source files, or command arguments. The
script infers the account and creates `ACCOUNT/noor-islamic-assistant`, uploading
only app files, source data, notices, dependencies, and deployment helpers.
Existing Spaces require an explicit `--space-id ACCOUNT/NAME --update`. The token
is used only to publish, and is not uploaded or needed by the running app.

After the Space finishes building, use its actual app URL for readiness checks:

```bash
uv run --frozen python scripts/smoke.py --base-url "$NOOR_CLOUD_URL"
uv run --frozen python scripts/model_smoke.py --base-url "$NOOR_CLOUD_URL"
```

The model check must pass in both English and Hindi. A successful upload, source
retrieval fallback, or `model_enabled=true` does not establish live inference.
The prepared configuration alone does not create a live website. Hosting account
access and a successful build are required.

Current validation: the 44-test suite, cloud container, cited source requests,
and browser storage checks passed. Live English explanations passed after
restricting citation generation to supplied evidence IDs. The default small
model's Hindi explanation check failed; Noor rejects that response and displays
the verified Hindi passages instead. A larger model download was interrupted by
the cloud environment restart and then blocked by the network proxy. Hindi model
explanations and the public hosted deployment still require successful validation.

## Development on a server

Python 3.11+ and [uv](https://docs.astral.sh/uv/) are required.

```bash
cd /workspace/Copilot
export UV_CACHE_DIR=/workspace/.cache/uv
uv sync --locked
uv run --frozen uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open the running application's port 8000 in your development or hosting environment. To test the service from the same machine:

```bash
uv run --frozen python scripts/smoke.py
uv run --frozen pytest -q
```

On another machine, use your own checkout directory and a writable uv cache. The source library needs no database or secret. Ollama explanations are enabled by default and require the local model setup below; if the model is unavailable, the app displays retrieved sources and an explicit notice.

## What works

- Topic questions: charity, prayer, fasting, mercy, patience, intentions, parents, knowledge, and kindness.
- Quran references: `2:177`, `112:1-4`, multiple references, or `Surah 112`.
- Surah names: Al-Fatiha, Al-Ikhlas, Al-Falaq, and An-Nas. Use numeric references for other chapters. To avoid silently shortening passages, requests are limited to 20 verses at once.
- English or Hindi responses, including an English question answered in Hindi. Explicit language instructions override the selected response language.
- Simple translation follow-ups such as `Translate that into Hindi` or `हिंदी में` reuse the last sourced question in the current page.
- Selected Hadith references: Muslim 612a, Bukhari 1, 13, 528, and 1410. Their original summaries are clearly distinguished from verbatim translations. Collection numbering follows the linked Sunnah.com references and can differ by edition.
- A sources panel with edition versions, licensing information, provenance, and the full Tanzil notice.

The application first retrieves local evidence. For a valid Quran passage that is missing locally, it can fetch the same approved, licensed JSON snapshot from `raw.githubusercontent.com`. It verifies the full file's pinned SHA-256 digest before accepting text. The complete bundled Quran normally makes that fallback unnecessary. It is a fixed source API, not unrestricted web search, a live edition update, or an external Hadith search engine.

For unsupported requests, Noor says it lacks verified sources and asks for a precise reference. It never claims to have searched an API unless that lookup occurred. Lexical search retrieves related passages, not a conclusive religious ruling.

## Open-weight model on the application server (Ollama)

Ollama explanations are enabled by default. Run [Ollama](https://github.com/ollama/ollama) on the application server and download `qwen2.5:1.5b`, an Apache-2.0 model. The cloud image handles this automatically. Review its model card and the exact downloaded artifact before redistribution. Model weights are not included in Git. Set `NOOR_OLLAMA_ENABLED=false` to use only retrieved source passages.

```bash
ollama serve
# In another terminal:
ollama pull qwen2.5:1.5b
export NOOR_OLLAMA_ENABLED=true
export NOOR_OLLAMA_URL=http://127.0.0.1:11434
export NOOR_OLLAMA_MODEL=qwen2.5:1.5b
uv run --frozen uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The server must restart after configuration changes. A reachable loopback model endpoint and downloaded model are required. Noor sends the question and up to four source excerpts to Ollama with the system prompt in `app/prompts.py`; it accepts structured output with known evidence IDs. Unknown citations, newly invented Quran references, external links, quoted passages, and a non-Hindi answer to a Hindi request are rejected. If Ollama or its model is unavailable, the original passages are still shown with an explicit notice. These checks do not prove every model explanation is correct; the interface labels generated explanations for review.

To require actual English and Hindi model explanations after downloading the model and starting Noor:

```bash
uv run --frozen python scripts/model_smoke.py
```

This check fails when model inference is unavailable, rejected, or replaced by source retrieval.

Environment settings are described in `.env.example`. The application reads exported environment variables; it does not automatically load that example file. `NOOR_ENABLE_EXTERNAL=false` disables source API fallback. No credentials are required, and the model destination is restricted to loopback.

## Sources and copyright

Citations identify a source; they do not grant permission to republish it. This application preserves licensed content and separates the application license from source licenses:

| Material | Provenance and terms |
| --- | --- |
| Application code and original Hadith summaries | MIT; see `LICENSE` |
| Dataset mirror and metadata | [risan/quran-json](https://github.com/risan/quran-json), CC BY-SA 4.0; pinned revision in `data/manifest.json` |
| Arabic text | Tanzil Project, CC BY 3.0 with **verbatim-only** terms; full notice in `data/licenses/TANZIL.txt` |
| English meanings | QuranEnc.com, English Translation — Noor International Center, version 1.1.2 |
| Hindi meanings | QuranEnc.com, Azizul Haq Al-Omari, version 1.1.5 |
| Translations and footnotes | QuranEnc republication terms; source metadata, original wording, and footnotes retained |

The Quran data was obtained from the license-documented mirror, not by scraping websites. The Arabic text retains the mirror's Tanzil convention of an opening basmala in the first verse of most chapters. Published translations and footnotes contain the translator's interpretation; they are not represented as an independent consensus. Hadith summaries are original paraphrases of the linked references, not copied Sunnah.com translations.

Before public distribution, verify the current [QuranEnc editions and terms](https://quranenc.com/en/home/api), retain attribution and transcript information, report corrections to the publisher, and keep translations current. Do not edit wording or strip footnotes to fit a response. Dataset checksums ensure this pinned copy is unchanged; they do not establish that it is the latest edition. Review Hadith summaries and generated explanations with qualified subject-matter reviewers. The application does not promise that every future source or generated output is free of copyright obligations.

## API

`GET /api/health` checks the loaded knowledge library. `GET /api/sources` returns provenance and license metadata. `POST /api/chat` accepts:

```json
{"question":"What does the Quran say about charity?","language":"en","scope":"all","allow_external":true}
```

`language` is `en` or `hi`; `scope` is `all`, `quran`, or `hadith`. An optional `context_question` supports a translation follow-up. Questions are limited to 2,000 characters. The response includes the user's `query`, `response`, `citations`, the local/API source mode, the model status, and any limitations. The UI labels messages **Query** and **Response**. The prompt used for optional model explanations is in `app/prompts.py`. Interactive API documentation is served at `/docs`.

## Deployment

The Dockerfile packages the application with dependencies pinned and hash-verified in `requirements.txt`, and runs it as a non-root user. It can run on a self-hosted open-source platform such as Coolify or Dokku. No deployment is performed automatically.

The combined cloud image preserves Ollama, GGML, and Qwen license notices in
`runtime-licenses/`, from `deploy/licenses/`. These runtime and model terms are
separate from the application and Quran data licenses.

```bash
docker compose up --build -d
```

For model explanations, include the Ollama service, which shares the application network namespace and persists model downloads:

```bash
NOOR_OLLAMA_ENABLED=true docker compose --profile llm up --build -d
docker compose --profile llm exec ollama ollama pull qwen2.5:1.5b
```

Docker and real model inference must be verified in the target host; their configuration is supplied but not assumed to have been executed. The model may require several GB of RAM. Keep the Ollama port private. Public hosting should place the application behind HTTPS and add an appropriate access/rate limit at the hosting proxy. Chats are kept only in browser memory; the server has no conversation database. Default access logs contain endpoint paths, not question bodies. Optional model requests are processed by the local model service.

In the Codex cloud machine, Docker builds need the supplied proxy DNS mapping and system trust bundle. The helper below passes the existing proxy through Docker's standard proxy arguments and mounts the public CA bundle as a build secret. TLS verification and package-hash checks remain enabled; the bundle is not stored in the image.

```bash
uv run --frozen python scripts/build_cloud_container.py
```

For Ollama in this cloud machine, the following helper starts the official image pinned to a verified digest, binds it only to loopback, preserves its state in `/workspace/.cache/ollama`, and uses the existing proxy and trusted CA bundle:

```bash
uv run --frozen python scripts/start_cloud_ollama.py
uv run --frozen python scripts/pull_cloud_model.py
```

Model downloads require `registry.ollama.ai` and any blob-storage hosts returned by that registry to be allowed in environment settings. Saving a network configuration draft does not apply it to the running machine. If a download is denied, apply the required network settings and retry it before claiming that model explanations work. Neither model weights nor Ollama's generated local keys belong in Git.

For the configured `qwen2.5:1.5b` artifact, the observed blob-storage hostname is `dd20bb891979d25aebc8bec07b2b3bbc.r2.cloudflarestorage.com`. The downloader prints destination hostnames without disclosing signed download URLs when access is denied.

## Layout

```text
app/             FastAPI server, retrieval, approved source API, model adapter
app/static/      Responsive chat interface; no frontend build step
data/            Licensed Quran snapshots, metadata, original Hadith summaries
data/licenses/   Preserved third-party terms and notices
tests/           Source, language, fallback, model, and HTTP integration checks
scripts/smoke.py Functional validation against a running application
```
