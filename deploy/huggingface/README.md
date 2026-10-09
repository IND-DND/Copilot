---
title: Noor · Islamic knowledge assistant
emoji: 🌙
colorFrom: green
colorTo: yellow
sdk: docker
app_port: 7860
license: mit
suggested_hardware: cpu-basic
startup_duration_timeout: 1h
fullWidth: true
header: mini
models:
  - Qwen/Qwen2.5-1.5B-Instruct
---

# Noor

Explore the Quran and selected Hadith references in English and Hindi, with
Arabic text, citations, preserved translator footnotes, and optional explanations
from the open-weight Qwen2.5 model through Ollama.

The app, text library, and model run on this cloud server. Visitors need only a
browser. No installation, model download, cookies, or saved chat history is
required on their computer. Responses and app assets request `Cache-Control:
no-store`. Conversations live in page memory and disappear on reload.

The model downloads on the **cloud server** at first startup. While it downloads,
or if the download fails, Noor serves cited passages and explicitly reports that
model explanations are unavailable. The health endpoint checks the source
library; it does not prove model inference. See the repository's live model smoke
test before treating the model as ready. Ephemeral server storage is cleared on
Space recreation; weights may need to download again. No persistent volume or
conversation database is configured.

The default small model's English explanation check passed in the development
cloud. Its Hindi explanation check failed; verified Hindi passages remain
available through source retrieval. Full model readiness requires passing both
language checks on the deployed host.

`NOOR_OLLAMA_ENABLED=false` deliberately selects source retrieval only. Ollama
listens on server loopback; only the web app is exposed. This image targets CPU
hosting. Hardware and availability are controlled by the hosting account; this
metadata does not purchase upgraded hardware.

Code and original Hadith summaries are MIT licensed. Quran data has separate
terms: the mirror is CC BY-SA 4.0, Arabic is Tanzil CC BY 3.0 with verbatim-only
conditions, and translations retain QuranEnc edition metadata and footnotes.
Full notices are in `data/licenses/` and in the app's sources panel. Generated
explanations are labeled and can be incorrect. Consult a qualified scholar for
personal rulings.

Source and deployment documentation: https://github.com/IND-DND/Copilot
