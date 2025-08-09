from pydantic import BaseModel, HttpUrl
from typing import Optional


class PodcastRequest(BaseModel):
    text: str
    voice: Optional[str] = "en"


class PodcastResponse(BaseModel):
    script: str
    audio_url: HttpUrl
