from __future__ import annotations

import re
from gtts import gTTS

# Precompiled patterns
_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)
_EMAIL_RE = re.compile(r"\b\S+@\S+\b")
_LABEL_RE = re.compile(r"\[(?:Host|Speaker)\s*[A-Z]\]\s*", re.I)
_COLON_LABEL_RE = re.compile(r"^(?:Host|Speaker)\s*[A-Z]\s*:\s*", re.I | re.M)
_NONWORD_RUN_RE = re.compile(r"[_*/#=<>{}\\\[\]|`~^]+")


def clean_for_tts(text: str) -> str:
    """Make text friendlier for TTS:
    - remove host labels like "[Host A]" or "Host A:"
    - strip URLs/emails/code-ish tokens
    - de-hyphenate line-break splits
    - collapse noisy symbol runs and whitespace
    - keep everything in English ASCII-ish where possible
    """
    # Remove labels such as "[Host A]" and line-leading "Host A:"
    text = _LABEL_RE.sub("", text)
    text = _COLON_LABEL_RE.sub("", text)

    # Remove URLs and emails
    text = _URL_RE.sub("", text)
    text = _EMAIL_RE.sub("", text)

    # De-hyphenate split words across newlines: "exam-\nple" -> "example"
    text = re.sub(r"-\s*\n\s*", "", text)

    # Remove long symbol runs (tables/code artifacts)
    text = _NONWORD_RUN_RE.sub(" ", text)

    # Replace odd bullets with commas
    text = re.sub(r"[•·]\s*", ", ", text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def text_to_speech(text: str, filename: str) -> None:
    cleaned = clean_for_tts(text)
    tts = gTTS(cleaned, lang="en")
    tts.save(filename)
