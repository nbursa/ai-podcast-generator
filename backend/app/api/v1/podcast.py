from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, HttpUrl, Field

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.services.tts_service import text_to_speech
from pathlib import Path

# --- Materials/script helpers ---
from typing import Iterable, List, Optional, Dict, Any, Literal
from app.services.openai_service import generate_script, generate_script_from_pillar
import json

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None  # type: ignore
# -------------------------------
# Materials ingestion helpers
# -------------------------------


def _load_content_pillar(dirs: Iterable[str]) -> Optional[Dict[str, Any]]:
    """Search materials directories for a content pillar JSON and return it as dict.
    Preference: files named like 'content_pillar*.json' or containing a top-level 'topics' or 'sections' list.
    """
    candidates: list[str] = []
    for base in dirs:
        if not base:
            continue
        base_abs = os.path.abspath(base)
        if not os.path.exists(base_abs):
            continue
        for root, _, files in os.walk(base_abs):
            for name in files:
                lower = name.lower()
                if lower.endswith(".json") and (
                    "content_pillar" in lower or "pillar" in lower
                ):
                    candidates.append(os.path.join(root, name))
    if not candidates:
        for fp in _iter_material_files(dirs):
            if fp.lower().endswith(".json"):
                candidates.append(fp)
    for fp in candidates:
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            # Unwrap common wrapper
            if (
                isinstance(data, dict)
                and "output" in data
                and isinstance(data["output"], dict)
            ):
                inner = data["output"]
            else:
                inner = data
            # Accept classic pillar (topics/sections) OR chunked OCR-like structure
            if isinstance(inner, dict) and (
                "topics" in inner or "sections" in inner or "chunks" in inner
            ):
                return inner
        except Exception:
            continue
    return None


def _iter_material_files(dirs: Iterable[str]) -> Iterable[str]:
    for base in dirs:
        if not base:
            continue
        base = os.path.abspath(base)
        if not os.path.exists(base):
            continue
        for root, _, files in os.walk(base):
            for name in files:
                if name.lower().endswith((".txt", ".md", ".json", ".pdf")):
                    yield os.path.join(root, name)


def _read_file_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in {".txt", ".md"}:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception:
            return ""
    if ext == ".json":
        try:
            import json

            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            # Compact representation for prompting
            return "JSON\n" + (data if isinstance(data, str) else str(data))
        except Exception:
            return ""
    if ext == ".pdf" and PdfReader is not None:
        try:
            reader = PdfReader(path)
            pages = []
            for p in reader.pages:
                try:
                    pages.append(p.extract_text() or "")
                except Exception:
                    pages.append("")
            return "\n".join(pages)
        except Exception:
            return ""
    return ""


def _load_materials_text(dirs: Iterable[str]) -> str:
    chunks: list[str] = []
    PER_FILE_CAP = 200_000  # ~200k chars per file (~30–40k words)
    GLOBAL_CAP = 500_000  # ~500k chars across all files
    total = 0
    for fp in _iter_material_files(dirs):
        text = _read_file_text(fp)
        if not text:
            continue
        snippet = text[:PER_FILE_CAP]
        header = f"\n--- FILE: {os.path.basename(fp)} ---\n"
        block = header + snippet
        if total + len(block) > GLOBAL_CAP:
            remaining = max(0, GLOBAL_CAP - total)
            if remaining <= len(header):
                break
            block = header + snippet[: remaining - len(header)]
        chunks.append(block)
        total += len(block)
        if total >= GLOBAL_CAP:
            break
    return "\n".join(chunks)


def _resolve_materials_dirs(materials_set: Optional[Literal["1", "2"]]) -> list[str]:
    # Default to set "1" if not provided
    defaults = list(settings.materials_dirs)
    if not defaults:
        return []
    if materials_set == "2" and len(defaults) >= 2:
        return [defaults[1]]
    # materials_set == "1" or anything else -> first dir
    return [defaults[0]]


def _build_prompt(
    title: str | None, description: str | None, materials_text: str
) -> str:
    intro = (f"Title: {title}\n" if title else "") + (
        f"Description: {description}\n" if description else ""
    )
    guide = (
        "\nWrite a complete conversational podcast script in clear US English with TWO hosts (Host A and Host B).\n"
        "Requirements: natural dialogue, faithful to the provided notes, no invented facts, smooth transitions.\n"
        "Structure: intro, 3–6 topical segments with back-and-forth discussion, and an outro with concise takeaways.\n"
        "Aim for a substantial episode (roughly 8–12 minutes of audio).\n"
    )
    sources = "\nSOURCE NOTES (from PDFs/JSON):\n" + materials_text
    return intro + guide + sources


router = APIRouter(prefix="/v1/podcasts", tags=["podcasts"])


class _State(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    voice: Optional[str] = None
    script: Optional[str] = None
    source_urls: List[HttpUrl] = []
    status: str = "queued"  # queued | running | done | failed | cancelled
    progress: float = 0.0  # 0..1
    audio_url: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    materials_set: Optional[Literal["1", "2"]] = None


_STORE: Dict[str, _State] = {}


def _bootstrap_from_storage() -> int:
    """Scan the storage directory for existing MP3s and load them into the in‑memory store.

    Returns the number of episodes added.
    """
    added = 0
    try:
        storage = Path(settings.storage_dir)
        if not storage.exists():
            return 0
        for mp3 in storage.glob("*.mp3"):
            try:
                episode_id = mp3.stem  # filename without extension
                if episode_id in _STORE:
                    continue
                stat = mp3.stat()
                ts = datetime.utcfromtimestamp(stat.st_mtime)
                _STORE[episode_id] = _State(
                    id=episode_id,
                    title=f"Episode {episode_id}",
                    description=None,
                    voice=None,
                    script=None,
                    source_urls=[],
                    status="done",
                    progress=1.0,
                    audio_url=f"/media/audio/{mp3.name}",
                    error=None,
                    created_at=ts,
                    updated_at=ts,
                )
                added += 1
            except Exception:
                # ignore a single bad file and continue
                continue
    except Exception:
        return added
    return added


# -------------------------------
# Schemas
# -------------------------------
class PodcastCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    voice: Optional[str] = Field(None, description="e.g. 'alloy', 'ava', 'baritone'")
    script: Optional[str] = Field(
        None,
        description="If provided, it will be used directly; otherwise it will be generated from the sources.",
    )
    source_urls: List[HttpUrl] = Field(
        default_factory=list,
        description="URLs of sources for the podcast. Can be empty.",
    )
    materials_set: Optional[Literal["1", "2"]] = Field(
        None,
        description="Pick which materials set to use: '1' or '2'. Defaults to '1'.",
    )


class PodcastCreateResponse(BaseModel):
    id: str


class PodcastStatusResponse(BaseModel):
    id: str
    status: str
    progress: float
    title: str
    description: Optional[str] = None
    voice: Optional[str] = None
    audio_url: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PodcastListResponse(BaseModel):
    items: List[PodcastStatusResponse]
    total: int


# -------------------------------
# “Generation” stub
# -------------------------------
async def _generate_podcast(podcast_id: str) -> None:
    """
    Hook up your service layer here:
    - generate the script (if not provided)
    - synthesize speech
    - save the file and set audio_url
    - handle errors and set status/message
    """
    state = _STORE.get(podcast_id)
    if not state or state.status in {"cancelled", "failed", "done"}:
        return

    try:
        state.status = "running"
        state.updated_at = datetime.utcnow()

        # 1) Script generation phase
        for i in range(1, 4):
            await asyncio.sleep(0.4)
            state.progress = i / 10.0  # 0.1, 0.2, 0.3
            state.updated_at = datetime.utcnow()

            if not state.script:
                selected_dirs = _resolve_materials_dirs(state.materials_set)
                pillar = _load_content_pillar(selected_dirs)
                if pillar:
                    state.script = generate_script_from_pillar(pillar)
                else:
                    materials_text = _load_materials_text(selected_dirs)
                    if materials_text.strip():
                        prompt = _build_prompt(
                            state.title, state.description, materials_text
                        )
                        state.script = generate_script(prompt)
                    else:
                        joined = (
                            ", ".join(str(u) for u in state.source_urls) or "no sources"
                        )
                        state.script = (
                            f"[Auto-script] Podcast '{state.title}'. "
                            f"Sources: {joined}. This is a demo script — replace with the actual generated content."
                        )
                state.updated_at = datetime.utcnow()

        # 2) TTS step — synthesize speech and save file
        os.makedirs(settings.storage_dir, exist_ok=True)
        output_filename = f"{podcast_id}.mp3"
        output_path = os.path.join(settings.storage_dir, output_filename)

        # synthesize
        text_to_speech(state.script or state.title, output_path)

        # progress
        state.progress = 0.9
        state.updated_at = datetime.utcnow()

        # 3) set audio_url
        state.audio_url = f"/media/audio/{output_filename}"
        state.progress = 1.0
        state.status = "done"
        state.updated_at = datetime.utcnow()

    except Exception as exc:  # noqa: BLE001
        state.status = "failed"
        state.error = str(exc)
        state.updated_at = datetime.utcnow()


def _as_status(state: _State) -> PodcastStatusResponse:
    return PodcastStatusResponse(
        id=state.id,
        status=state.status,
        progress=state.progress,
        title=state.title,
        description=state.description,
        voice=state.voice,
        audio_url=state.audio_url,
        error=state.error,
        created_at=state.created_at,
        updated_at=state.updated_at,
    )


# -------------------------------
# Routes
# -------------------------------
@router.post("", response_model=PodcastCreateResponse, status_code=202)
async def create_podcast(
    payload: PodcastCreateRequest, bg: BackgroundTasks
) -> PodcastCreateResponse:
    podcast_id = str(uuid.uuid4())

    state = _State(
        id=podcast_id,
        title=payload.title,
        description=payload.description,
        voice=payload.voice,
        script=payload.script,
        source_urls=payload.source_urls or [],
        status="queued",
        progress=0.0,
        materials_set=payload.materials_set,
    )
    _STORE[podcast_id] = state

    # start bg task
    bg.add_task(_generate_podcast, podcast_id)

    return PodcastCreateResponse(id=podcast_id)


@router.get("/{podcast_id}", response_model=PodcastStatusResponse)
async def get_podcast(podcast_id: str) -> PodcastStatusResponse:
    state = _STORE.get(podcast_id)
    if not state:
        raise HTTPException(status_code=404, detail="Podcast not found")
    return _as_status(state)


@router.get("", response_model=PodcastListResponse)
async def list_podcasts(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(
        None, description="Filter by status: queued|running|done|failed|cancelled"
    ),
) -> PodcastListResponse:
    items = list(_STORE.values())
    if status:
        items = [s for s in items if s.status == status]
    total = len(items)
    items = items[offset : offset + limit]
    return PodcastListResponse(items=[_as_status(s) for s in items], total=total)


@router.delete("/{podcast_id}", response_model=PodcastStatusResponse)
async def cancel_or_delete_podcast(podcast_id: str) -> PodcastStatusResponse:
    state = _STORE.get(podcast_id)
    if not state:
        raise HTTPException(status_code=404, detail="Podcast not found")

    # If already done, "delete" from store
    if state.status in {"done", "failed"}:
        removed = _STORE.pop(podcast_id)
        # delete associated audio file
        try:
            audio_path = os.path.join(settings.storage_dir, f"{podcast_id}.mp3")
            if os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception:
            pass
        return _as_status(removed)

    # Otherwise, mark as cancelled
    state.status = "cancelled"
    state.updated_at = datetime.utcnow()
    return _as_status(state)


# Health-ish endpoint for debugging
@router.get("/_debug/{podcast_id}")
async def debug_raw_state(podcast_id: str) -> Dict[str, Any]:
    state = _STORE.get(podcast_id)
    if not state:
        raise HTTPException(status_code=404, detail="Podcast not found")
    return state.model_dump()


# Manual rescan endpoint
@router.post("/_rescan")
async def rescan_storage() -> Dict[str, Any]:
    count = _bootstrap_from_storage()
    return {"added": count, "total": len(_STORE)}


# -------------------------------
# FastAPI app bootstrap (entrypoint)
# -------------------------------
app = FastAPI(title="AI Podcast Generator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure storage dir exists before mounting static files (Starlette checks at import time)
os.makedirs(settings.storage_dir, exist_ok=True)


# make sure storage exists
@app.on_event("startup")
def _startup() -> None:
    os.makedirs(settings.storage_dir, exist_ok=True)
    _bootstrap_from_storage()


# Serve static files for audio
app.mount(
    "/media/audio",
    StaticFiles(directory=settings.storage_dir, check_dir=False),
    name="audio",
)

# Include routes
app.include_router(router)


# Health endpoint
@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
