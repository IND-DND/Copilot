from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import ROOT, Settings
from .engine import Engine
from .knowledge import Knowledge
from .providers import LocalModel, QuranSourceAPI
from .schemas import ChatRequest, ChatResponse


def create_app(settings=None):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        knowledge = Knowledge(settings.data_dir)
        app.state.knowledge = knowledge
        app.state.engine = Engine(knowledge, QuranSourceAPI(knowledge), LocalModel(settings), settings)
        yield

    app = FastAPI(title="Noor · Islamic Knowledge Assistant", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        if request.url.path == "/" or request.url.path.startswith("/static"):
            response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'self' https://huggingface.co; base-uri 'none'; form-action 'self'"
        return response

    @app.get("/api/health")
    async def health():
        kb = app.state.knowledge
        return {"status": "ok", "quran_verses": len(kb.index["en"]), "hadith_summaries": len(kb.hadith), "languages": ["en", "hi"], "external_lookup_enabled": settings.external_enabled, "model_enabled": settings.ollama_enabled, "model": settings.ollama_model if settings.ollama_enabled else None}

    @app.get("/api/sources")
    async def sources():
        kb = app.state.knowledge
        return {"quran": kb.manifest, "hadith": [{"reference": h["reference"], "url": h["url"], "note": h["note"]} for h in kb.hadith]}

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest):
        return await app.state.engine.answer(request)

    @app.get("/")
    async def index():
        return FileResponse(ROOT / "app/static/index.html")

    app.mount("/static", StaticFiles(directory=ROOT / "app/static"), name="static")
    return app


app = create_app()
