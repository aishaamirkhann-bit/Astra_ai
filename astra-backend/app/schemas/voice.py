from pydantic import BaseModel, ConfigDict, Field


class TranscribeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transcript: str
    language: str | None = None
    provider: str = "browser-fallback"


class SynthesizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)
    voice: str | None = None
    language: str | None = None
