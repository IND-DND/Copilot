from typing import Literal

from pydantic import BaseModel, Field, field_validator

Language = Literal["en", "hi"]


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    language: Language = "en"
    scope: Literal["all", "quran", "hadith"] = "all"
    allow_external: bool = True
    context_question: str | None = Field(default=None, max_length=2000)

    @field_validator("question")
    @classmethod
    def clean_question(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Please enter a question.")
        return value


class Evidence(BaseModel):
    id: str
    reference: str
    kind: Literal["quran", "hadith"]
    arabic: str | None = None
    text: str
    footnotes: str = ""
    url: str
    publisher: str
    version: str
    license: str
    license_url: str
    origin: Literal["local", "api"] = "local"
    note: str = ""


class ChatResponse(BaseModel):
    query: str
    retrieval_query: str
    response: str
    language: Language
    citations: list[Evidence]
    mode: Literal["retrieval", "model", "no_sources"]
    source_mode: Literal["local", "api", "mixed", "none"]
    model_status: Literal["disabled", "used", "unavailable", "rejected"]
    notices: list[str] = Field(default_factory=list)
