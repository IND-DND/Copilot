import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    data_dir: Path = ROOT / "data"
    external_enabled: bool = True
    ollama_enabled: bool = True
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:1.5b"

    @classmethod
    def from_env(cls):
        return cls(
            external_enabled=os.getenv("NOOR_ENABLE_EXTERNAL", "true").lower() == "true",
            ollama_enabled=os.getenv("NOOR_OLLAMA_ENABLED", "true").lower() == "true",
            ollama_url=os.getenv("NOOR_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/"),
            ollama_model=os.getenv("NOOR_OLLAMA_MODEL", "qwen2.5:1.5b"),
        )
