import pytest
from fastapi.testclient import TestClient

from app.config import ROOT, Settings
from app.knowledge import Knowledge
from app.main import create_app


@pytest.fixture(scope="session")
def knowledge():
    return Knowledge(ROOT / "data")


@pytest.fixture(scope="session")
def client():
    with TestClient(create_app(Settings(ollama_enabled=False))) as client:
        yield client
