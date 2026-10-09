"""Free Gradio deployment. Chat contents stay in session memory only."""

import asyncio
import logging
import os
from html import escape
from urllib.parse import urlsplit

from .config import ROOT, Settings
from .engine import Engine, TEXT
from .knowledge import Knowledge
from .model_output import checked_summary, model_messages
from .providers import LocalModel, QuranSourceAPI
from .schemas import ChatRequest


class NoStoreMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        async def no_store(message):
            if message["type"] == "http.response.start":
                headers = [(key, value) for key, value in message.get("headers", []) if key.lower() not in {b"cache-control", b"pragma"}]
                message["headers"] = headers + [(b"cache-control", b"no-store"), (b"pragma", b"no-cache")]
            await send(message)
        await self.app(scope, receive, no_store)


def link(url, label):
    if urlsplit(url).scheme != "https":
        return escape(label)
    return f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{escape(label)}</a>'


def render(answer, arabic_notice):
    hi = answer.language == "hi"
    content = [f'<section class="noor-result"><h3>Query · प्रश्न</h3><p>{escape(answer.query)}</p>',
               f'<h3>Response · उत्तर</h3><p lang="{answer.language}">{escape(answer.response)}</p>']
    if answer.mode == "model":
        content.append('<p class="noor-meta">AI explanation · Review the cited sources / स्रोतों की जाँच करें</p>')
    for notice in answer.notices:
        content.append(f'<p class="noor-notice">{escape(notice)}</p>')
    for source in answer.citations:
        content.append(f'<article class="noor-source"><h4>{link(source.url, source.reference)}</h4>')
        if source.arabic:
            content.append(f'<p class="noor-arabic" dir="rtl" lang="ar">{escape(source.arabic)}</p>')
        content.append(f'<p lang="{answer.language}">{escape(source.text)}</p>')
        if source.footnotes:
            content.append(f'<details><summary>{"अनुवादक की टिप्पणियाँ" if hi else "Translator footnotes"}</summary><p>{escape(source.footnotes)}</p></details>')
        content.append(f'<p class="noor-meta">{escape(source.publisher)} · Version {escape(source.version)}<br>{link(source.license_url, source.license)}</p>')
        if source.note:
            content.append(f'<p class="noor-meta">{escape(source.note)}</p>')
        content.append('</article>')
    if any(s.arabic for s in answer.citations):
        content.append(f'<details><summary>Arabic text attribution &amp; terms</summary><p>{escape(arabic_notice)}</p></details>')
    return ''.join(content) + '</section>'


def answer_question(engine, generator, question, language, scope, use_model, context_question):
    request = ChatRequest(question=question, language=language, scope=scope, context_question=context_question or None)
    # Complete retrieval before requesting a shared GPU; no sources means no inference.
    answer = asyncio.run(engine.answer(request))
    if use_model and answer.citations:
        sources = answer.citations[:4]
        try:
            output = generator(model_messages(answer.retrieval_query, answer.language, sources))
            summary, status = checked_summary(output, answer.language, sources)
        except Exception as error:
            # GPU queue/quota and transient model errors must not hide source passages.
            reason = "gpu_quota" if "quota" in str(error).lower() else "gpu_runtime"
            logging.getLogger(__name__).warning("Model unavailable: %s (%s)", reason, type(error).__name__)
            summary, status = None, "unavailable"
            if reason == "gpu_quota":
                answer.notices.append(
                    "मुफ़्त GPU कोटा उपलब्ध नहीं है। अपने खाते का कोटा इस्तेमाल करने के लिए Hugging Face में साइन इन करें, या स्रोत पढ़ने के लिए AI व्याख्या बंद करें।"
                    if answer.language == "hi" else
                    "Free GPU quota is unavailable. Sign in to Hugging Face for your account's quota, or switch off AI explanation to continue reading sources."
                )
        answer.model_status = status
        if summary:
            answer.response, answer.mode = summary, "model"
        else:
            answer.notices.append(TEXT[answer.language]["model_" + status])
    return answer


CSS = """
.gradio-container { max-width: 1000px !important; }
.noor-result { line-height: 1.8; overflow-wrap: anywhere; }
.noor-source { padding: 20px; border: 1px solid #b8c8be; border-radius: 12px; margin: 18px 0; }
.noor-arabic { font-size: 1.7rem; line-height: 2.2; text-align: right; }
.noor-meta { font-size: .85rem; opacity: .8; }
.noor-notice { border-left: 3px solid #b78a3d; padding-left: 12px; }
.noor-result p { white-space: pre-wrap; }
"""


def build_ui(generator):
    # Gradio 6 otherwise records inputs and outputs in browser localStorage.
    os.environ["GRADIO_RUN_HISTORY"] = "false"
    import gradio as gr

    knowledge = Knowledge(ROOT / "data")
    settings = Settings(ollama_enabled=False)
    engine = Engine(knowledge, QuranSourceAPI(knowledge), LocalModel(settings), settings)
    notice = knowledge.manifest["arabic"]["notice"]

    def ask(question, language, scope, use_model, context_question):
        try:
            answer = answer_question(engine, generator, question, language, scope, use_model, context_question)
        except ValueError:
            raise gr.Error("Enter a question between 1 and 2,000 characters.") from None
        return render(answer, notice), answer.model_dump(), answer.retrieval_query if answer.citations else context_question

    with gr.Blocks(title="Noor · Islamic knowledge", analytics_enabled=False) as demo:
        gr.Markdown("# ✦ Noor\nExplore the Quran and selected Hadith in English or Hindi. Read exact source passages alongside a brief AI explanation.")
        gr.Markdown("**Free cloud hosting** · Model runs on Hugging Face ZeroGPU. Shared GPU queues and daily quotas apply; switch off AI explanation to read sources without using GPU time. No app installation, model download, or saved chat history on your computer.")
        context = gr.State(value="", time_to_live=3600)
        with gr.Row():
            language = gr.Dropdown([("English", "en"), ("हिंदी", "hi")], value="en", label="Response language")
            scope = gr.Dropdown([("Quran + Hadith", "all"), ("Quran", "quran"), ("Hadith", "hadith")], value="all", label="Sources")
        use_model = gr.Checkbox(value=True, label="Include AI explanation (uses free GPU quota)")
        question = gr.Textbox(label="Query · प्रश्न", placeholder="What does the Quran say about charity?", lines=2, max_lines=6)
        with gr.Row():
            submit = gr.Button("Ask Noor", variant="primary")
            clear = gr.Button("Clear conversation")
        gr.Examples([["What does the Quran say about charity?"], ["Translate Surah Al-Fatiha into Hindi"], ["What are the Hadiths about prayer times?"]], inputs=[question], cache_examples=False)
        output = gr.HTML()
        structured = gr.JSON(visible=False)
        arguments = dict(fn=ask, inputs=[question, language, scope, use_model, context], outputs=[output, structured, context], concurrency_limit=1)
        submit.click(**arguments, api_name="ask")
        question.submit(**arguments, api_name=False)
        clear.click(lambda: ("", "", None, ""), outputs=[question, output, structured, context], queue=False, api_name=False)
        gr.Markdown("Noor is an AI knowledge assistant. For personal religious rulings, consult a qualified scholar. The Hadith library contains five original summaries from Sunni collections; arbitrary website search is not available.")
        with gr.Accordion("Sources, attribution & model", open=False):
            gr.Markdown("Arabic Quran: [Tanzil](https://tanzil.net/docs/text_license), CC BY 3.0, verbatim. English and Hindi: [QuranEnc republication terms](https://quranenc.com/en/home/api/), published versions and footnotes preserved. [Dataset mirror](https://github.com/risan/quran-json), CC BY-SA 4.0; upstream terms apply. Hadith summaries are original explanations, with source references.\n\nCloud AI: [Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507), Apache 2.0. AI explanations are fallible and are separate from published translations.")
            gr.Textbox(value=notice, label="Complete Tanzil notice", interactive=False)
    return demo, CSS
