# AI Podcast Generator – Opinionated MVP

An end‑to‑end **podcast generation pipeline** that turns pre‑structured learning materials (PDF/JSON “content pillar”, notes, etc.) into a two‑host conversational **script** and an **MP3** via TTS. This is an **opinionated architecture / proof‑of‑concept**, not a turnkey product.

> **Non‑commercial demo.** The code is published for portfolio/demo purposes. If you intend to use it in production, please reach out for a commercial license and implementation.

---

## What this is

- A clean, modular backend that demonstrates the full flow: **ingest → script builder → TTS → storage/API**.
- Pluggable materials ingestion with sane defaults for:
  - custom JSON *content pillar* (topics/subtopics **or** OCR‐like `chunks[].text`),
  - PDFs/Markdown/TXT (basic text extraction).
- Two script paths:
  - **OpenAI‑powered** (when `OPENAI_API_KEY` is present),
  - **deterministic local fallback** (no API required) that builds a two‑host conversation from source text.
- Minimal, vendor‑neutral framing (no company branding in code/docs).

## What this isn’t

- Not a one‑click product. It expects **prepared inputs** and uses simple heuristics in fallback mode.
- Not a quality‑guaranteed copywriter. Without an LLM, the local builder produces readable but conservative scripts.

---

## Quickstart (backend)

Requirements: **Python 3.11+**, `poetry`, and optionally an OpenAI API key.

1. Install

    ```bash
    cd backend
    poetry install
    ```

2. Configure environment

    Create `backend/.env` (example):

    ```env
    PORT=3000
    BASE_URL=http://localhost:3000
    STORAGE_DIR=storage/episodes
    DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/podcast
    # Optional: enables LLM script generation
    OPENAI_API_KEY=sk-...
    # Materials root folders used by the API when materials_set is 1 or 2
    MATERIALS_DIRS=["/Users/nenad/Projects/ai-podcast-generator/materials/1","/Users/nenad/Projects/ai-podcast-generator/materials/2"]
    ```

3. Run

    ```bash
    poetry run uvicorn app.api.v1.podcast:app --reload --port 3000
    ```

4. Smoke test

    ```bash
    # Create a podcast from local materials set 1 (no URLs required)
    curl -X POST http://localhost:3000/v1/podcasts \
      -H "Content-Type: application/json" \
      -d '{
            "title":"Episode 1",
            "description":"From materials",
            "voice":"en",
            "materials_set":"1"
          }'

    # Poll status
    curl http://localhost:3000/v1/podcasts/<id-from-previous-response>

    # List finished items
    curl "http://localhost:3000/v1/podcasts?status=done"

    # Fetch audio (browser)
    open "http://localhost:3000/media/audio/<id>.mp3"
    ```

---

## API

### POST `/v1/podcasts`

Creates a background job.

#### **Body**

```json
{
  "title": "Episode title",               
  "description": "Optional description",  
  "voice": "en",                         
  "script": "(optional: if provided, used as-is)",
  "source_urls": [],                       
  "materials_set": "1"                    
}
```

- `materials_set`: chooses which local folder from `MATERIALS_DIRS` to ingest (`"1"` or `"2"`). If omitted, defaults to `"1"`.
- If `OPENAI_API_KEY` is present, the service will try an OpenAI‑based script generation; otherwise it uses a deterministic local builder.

#### **Response**

```json
{"id": "<uuid>"}
```

### GET `/v1/podcasts/{id}`

Returns status, progress, and `audio_url` once ready.

### GET `/v1/podcasts?status=done`

Lists finished items.

### DELETE `/v1/podcasts/{id}`

Cancels a running job or removes a finished/failed one from the in‑memory store.

### GET `/v1/podcasts/_debug/{id}`

Raw internal state dump (for debugging).

---

## How materials ingestion works

- The service searches the selected directory for a **content pillar** JSON (by name hint `content_pillar*.json` or by structure: `topics`/`sections` or `chunks`).
- If found, it builds the script from that structure. Otherwise, it falls back to reading **PDF/MD/TXT/JSON** files, concatenates excerpts, and generates a script from the combined text.
- Local fallback builder:
  - **Two hosts**: `Host A` and `Host B`
  - Intro → multiple segments → outro
  - Heuristics avoid URLs/tables and keep sentences readable

> The term *content pillar* here refers to a **custom JSON shape** used by the sample materials; it’s not a general standard.

---

## TTS

Default implementation uses **gTTS** (Google Text‑to‑Speech) with `lang="en"`. You can swap it for another engine.

Output files are saved under `STORAGE_DIR` and served at `/media/audio/<id>.mp3`.

---

## Roadmap ideas

- Streaming TTS + chunked playback
- Better pillar normalization and chunk prioritization
- Quality evaluation + guardrails for long numeric/token sequences
- Minimal web UI (upload, progress, embedded player)

---

## License

This project is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License - see the [LICENSE](LICENSE) file for details.
