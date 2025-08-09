from __future__ import annotations

from typing import Optional, TYPE_CHECKING, Any, Dict, List
import re as _re

# -------------------------------
# Sentence utilities for local generation
# -------------------------------
_DEF_SENT_SPLIT = _re.compile(r"(?<=[.!?])\s+")


def _readable_sentence(s: str) -> bool:
    s = s.strip()
    if len(s) < 20 or len(s) > 260:
        return False
    letters = sum(ch.isalpha() for ch in s)
    ratio = letters / max(1, len(s))
    if ratio < 0.55:
        return False
    if any(tok in s for tok in ("http://", "https://", "www.", "@", "#", "__")):
        return False
    return True


def _extract_sentences_from_chunks(pillar: Dict[str, Any]) -> list[str]:
    """Flatten `output.chunks[].text` or `chunks[].text` into readable sentences."""
    chunks = []
    if "chunks" in pillar and isinstance(pillar["chunks"], list):
        chunks = pillar["chunks"]
    elif (
        "output" in pillar
        and isinstance(pillar["output"], dict)
        and isinstance(pillar["output"].get("chunks"), list)
    ):
        chunks = pillar["output"]["chunks"]

    texts: list[str] = []
    for ch in chunks:
        t = ch.get("text") if isinstance(ch, dict) else None
        if not t or not isinstance(t, str):
            continue
        # Basic cleanup: collapse whitespace, drop heavy symbol runs
        t = _re.sub(r"[_*/#=<>{}\\\[\]|`~^]+", " ", t)
        t = _re.sub(r"\s+", " ", t).strip()
        if not t:
            continue
        sentences = [s.strip() for s in _DEF_SENT_SPLIT.split(t) if s.strip()]
        for s in sentences:
            if _readable_sentence(s):
                texts.append(s)
    return texts


# Static type alias for the OpenAI client (only used during type checking)
if TYPE_CHECKING:
    from openai import OpenAI as OpenAIType  # type: ignore
else:
    OpenAIType = Any  # at runtime we don't require the type

from app.core.config import settings

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

# Create a client only if a key is provided
_client: Optional[OpenAIType] = None
if settings.openai_api_key and OpenAI is not None:
    _client = OpenAI(api_key=settings.openai_api_key)


# -------------------------------
# Materials -> script (fallback path)
# -------------------------------


def _two_host_local_dialogue(materials_text: str) -> str:
    """Deterministic two‑host script built from materials text (no API).

    Produces an intro, several topical segments with back-and-forth, and an outro.
    Keeps everything in English and avoids inventing facts by quoting/condensing lines
    from the materials.
    """
    # Normalize newlines
    text = materials_text.replace("\r", "\n")

    # Remove obvious separators, but keep the content
    skip_prefixes = ("--- file:", "page ", "json:")
    raw_lines = [ln.strip() for ln in text.splitlines()]
    content_lines: list[str] = []
    for ln in raw_lines:
        if not ln:
            content_lines.append("")
            continue
        low = ln.lower()
        if low.startswith(skip_prefixes) or ln in {"{", "}", "[", "]"}:
            continue
        content_lines.append(ln)

    # Build paragraphs by merging short lines until we hit sentence-ending punctuation
    paragraphs: list[str] = []
    buf: list[str] = []

    def flush_buf() -> None:
        if buf:
            paragraph = " ".join(buf).strip()
            if paragraph:
                paragraphs.append(paragraph)
            buf.clear()

    for ln in content_lines:
        if not ln:
            flush_buf()
            continue
        buf.append(ln)
        # If the buffer is reasonably long and ends with sentence punctuation, flush
        joined = " ".join(buf)
        if len(joined) >= 220 and joined.rstrip().endswith((".", "!", "?")):
            flush_buf()
    flush_buf()

    # Fallback: if for some reason we didn't get paragraphs, treat entire text as one
    if not paragraphs:
        paragraphs = [" ".join([ln for ln in content_lines if ln]).strip()]

    def hostA(s: str) -> str:
        return f"[Host A] {s}"

    def hostB(s: str) -> str:
        return f"[Host B] {s}"

    def is_readable_sentence(s: str) -> bool:
        s = s.strip()
        if len(s) < 20 or len(s) > 260:
            return False
        letters = sum(ch.isalpha() for ch in s)
        ratio = letters / max(1, len(s))
        if ratio < 0.55:
            return False
        if any(token in s for token in ("http://", "https://", "www.", "@", "#", "__")):
            return False
        return True

    script: list[str] = []
    script.append(hostA("Welcome to the podcast."))
    script.append(
        hostB(
            "In this episode, we will walk through the provided materials in clear English and connect the ideas step by step."
        )
    )

    sent_split = _re.compile(r"(?<=[.!?])\s+")

    seg_idx = 1
    line_counter = 0
    for para in paragraphs:
        # Trim whitespace and split into sentences
        p = " ".join(para.split())
        sentences = [s.strip() for s in sent_split.split(p) if s.strip()]
        readable = [s for s in sentences if is_readable_sentence(s)]
        if not readable:
            continue

        # Segment header from the first readable sentence fragment
        title = readable[0]
        if len(title) > 90:
            title = title[:87] + "…"
        script.append(hostA(f"Segment {seg_idx}: {title}"))
        seg_idx += 1

        # Speak up to 5 sentences per paragraph, alternating speakers
        for j, s in enumerate(readable[:5]):
            speaker = hostA if (line_counter + j) % 2 == 0 else hostB
            # Light paraphrase starters to avoid robotic quoting but not add new facts
            if j == 0:
                spoken = f"Key point: {s}"
            elif j == 1:
                spoken = f"Put simply, {s[0].lower() + s[1:] if len(s) > 1 else s}"
            else:
                spoken = s
            script.append(speaker(spoken))
        line_counter += len(readable[:5])

        # Occasional connective tissue
        if seg_idx % 6 == 0:
            script.append(
                hostB(
                    "Quick recap so far: we are staying close to the source text and moving in order."
                )
            )

    script.append(hostA("That brings us to the end of today’s walkthrough."))
    script.append(
        hostB(
            "For full context, review the original materials alongside this episode. Thanks for listening."
        )
    )

    return "\n".join(script)


def generate_script(prompt: str) -> str:
    """Generate a two‑host conversational script from the prompt (which includes sources).

    If an OpenAI API key is configured, call the API; otherwise fall back to
    a deterministic local two‑host builder.
    """
    # Extract the materials slice to feed the local builder if needed
    materials_text = prompt
    if "SOURCE NOTES" in prompt:
        materials_text = prompt.split("SOURCE NOTES", 1)[1]

    if _client is None:
        return _two_host_local_dialogue(materials_text)

    try:
        resp = _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a careful writer. Produce a complete, natural two‑host conversation in clear US English. "
                        "Hosts are named 'Host A' and 'Host B'. Be faithful to the provided notes, avoid inventing facts, "
                        "use smooth transitions, and aim for an 8–12 minute episode."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
        )
        content = resp.choices[0].message.content if resp.choices else ""
        return content or _two_host_local_dialogue(materials_text)
    except Exception:
        return _two_host_local_dialogue(materials_text)


# -------------------------------
# Pillar-based script generation
# -------------------------------


def _two_host_local_from_pillar(pillar: Dict[str, Any]) -> str:
    """Deterministic two‑host script from a structured content pillar (no API).

    Accepts both classic structures (topics/sections) and chunked OCR-like pillars
    (with `chunks[].text`). Missing fields are handled gracefully.
    """

    def hostA(s: str) -> str:
        return f"[Host A] {s}"

    def hostB(s: str) -> str:
        return f"[Host B] {s}"

    title = (
        pillar.get("title") or pillar.get("document_title") or "the document"
    ).strip()
    topics: List[Dict[str, Any]] = pillar.get("topics") or pillar.get("sections") or []

    lines: List[str] = []
    lines.append(hostA("Welcome to the podcast."))
    lines.append(
        hostB(f"Today we dive into {title}, using the provided content as our guide.")
    )
    lines.append(
        hostA("We will move topic by topic and keep the language clear and practical.")
    )

    if isinstance(topics, list) and topics:
        for t_idx, topic in enumerate(topics, start=1):
            t_name = (
                topic.get("name") or topic.get("title") or f"Topic {t_idx}"
            ).strip()
            t_sum = (topic.get("summary") or topic.get("overview") or "").strip()
            lines.append(hostA(f"Segment {t_idx}: {t_name}"))
            if t_sum:
                lines.append(hostB(f"Big picture: {t_sum}"))
            subs = topic.get("subtopics") or topic.get("items") or []
            if isinstance(subs, list):
                for s_idx, sub in enumerate(subs, start=1):
                    s_name = (
                        sub.get("name") or sub.get("title") or f"Key point {s_idx}"
                    ).strip()
                    s_sum = (sub.get("summary") or sub.get("notes") or "").strip()
                    lines.append(hostA(f"— {s_name}."))
                    if s_sum:
                        lines.append(hostB(f"In short: {s_sum}"))
                if (t_idx % 3) == 0:
                    lines.append(
                        hostB(
                            "Quick recap so far: we are following the pillar structure and keeping close to its summaries."
                        )
                    )
    else:
        # No structured topics: fall back to chunked OCR-like structure
        sents = _extract_sentences_from_chunks(pillar)
        if not sents:
            lines.append(
                hostB(
                    "We received limited structured notes, so this will be a brief overview."
                )
            )
        else:
            seg = 1
            i = 0
            MAX_SENTS = 180  # cap to avoid excessively long local episodes
            sents = sents[:MAX_SENTS]
            while i < len(sents):
                # Take 5–7 sentences per segment
                window = sents[i : i + 7]
                if not window:
                    break
                title_line = window[0]
                if len(title_line) > 90:
                    title_line = title_line[:87] + "…"
                lines.append(hostA(f"Segment {seg}: {title_line}"))
                for j, s in enumerate(window):
                    speaker = hostA if (i + j) % 2 == 0 else hostB
                    if j == 0:
                        spoken = f"Key point: {s}"
                    elif j == 1:
                        spoken = (
                            f"Put simply, {s[0].lower() + s[1:] if len(s) > 1 else s}"
                        )
                    else:
                        spoken = s
                    lines.append(speaker(spoken))
                seg += 1
                step = max(5, min(7, len(window)))
                i += step
                if seg % 4 == 0:
                    lines.append(
                        hostB(
                            "Quick checkpoint: we’re moving in order and summarizing concisely."
                        )
                    )

    lines.append(hostA("That wraps up our walkthrough of the content pillar."))
    lines.append(
        hostB(
            "For full context, review the original documents alongside these notes. Thanks for listening."
        )
    )

    return "\n".join(lines)


def generate_script_from_pillar(pillar: Dict[str, Any]) -> str:
    """Generate a two‑host conversational script from a structured content pillar.

    Uses OpenAI if configured; otherwise falls back to a deterministic local builder.
    """
    if _client is None:
        return _two_host_local_from_pillar(pillar)

    try:
        resp = _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a careful writer. Produce a complete two‑host conversation in clear US English. "
                        "Hosts are 'Host A' and 'Host B'. Be faithful to the provided structured pillar (topics, subtopics, summaries, or chunks of text); "
                        "avoid inventing facts; use smooth transitions; aim for ~8–12 minutes."
                    ),
                },
                {"role": "user", "content": f"CONTENT PILLAR JSON:\n{pillar}"},
            ],
            temperature=0.4,
        )
        content = resp.choices[0].message.content if resp.choices else ""
        return content or _two_host_local_from_pillar(pillar)
    except Exception:
        return _two_host_local_from_pillar(pillar)
