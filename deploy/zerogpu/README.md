---
title: Noor Islamic Assistant
emoji: 🌙
colorFrom: green
colorTo: yellow
sdk: gradio
sdk_version: 6.30.0
python_version: 3.12
app_file: space_app.py
suggested_hardware: zero-a10g
startup_duration_timeout: 1h
license: mit
models:
  - Qwen/Qwen3-4B-Instruct-2507
fullWidth: true
---

# Noor · Free cloud Islamic knowledge assistant

Source-grounded Quran and selected Hadith questions, with exact Arabic, published English/Hindi translations, footnotes and source references. The optional AI explanation runs on shared Hugging Face ZeroGPU using the Apache-2.0 Qwen3-4B-Instruct-2507 model, pinned to revision `cdbee75f17c01a7cc42f958dc650907174af0554`.

This deployment uses Gradio/PyTorch instead of an Ollama daemon. Eligible free personal accounts can host two ZeroGPU Spaces. No paid hardware, persistent storage, or inference endpoint is requested. Visitors have daily GPU quotas and may queue; source-only responses do not consume GPU time. Free Spaces may sleep and need time to wake.

Model weights and source files are held on the cloud server. The application does not install anything or save conversation history in browser storage. Questions are sent to the public Hugging Face Space for processing; session context stays in server memory and expires after one hour. The platform's own operational logging and retention are governed by Hugging Face's policies.

The first startup downloads the cloud model. Invalid references or unavailable sources never request a GPU. GPU/quota failures and rejected model outputs return the verified passages with an explicit notice. AI explanations can be wrong; consult a qualified scholar for personal rulings.

Arabic: Tanzil CC BY 3.0, text and complete notice preserved. English/Hindi: QuranEnc republication terms, publisher/version/footnotes preserved. Dataset mirror: CC BY-SA 4.0; each underlying source retains its terms. Hadith: five original summaries with Sunni collection references. See `data/licenses/` and `deploy/licenses/QWEN-APACHE-2.0.txt`. Application code: MIT.

Structured generation uses LM Format Enforcer's public token API with an adapter
for Transformers 5. It restricts JSON citation IDs to the retrieved evidence.
Output language, new links/references, Arabic generation and quoted text are still
checked afterward. Formatting checks do not prove factual correctness. The
MIT license notice for the adapted tokenizer code is preserved in
`deploy/licenses/LM-FORMAT-ENFORCER-MIT.txt`.

Source repository: https://github.com/IND-DND/Copilot
