# Backend (FastAPI)

FastAPI service that ingests local learning materials and produces a two‑host podcast script + MP3 via TTS.

## Run locally

```bash
poetry install
poetry run uvicorn app.api.v1.podcast:app --reload --port 3000
```

Configure `.env` (example):

```env
PORT=3000
BASE_URL=http://localhost:3000
STORAGE_DIR=storage/episodes
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/podcast
OPENAI_API_KEY=sk-...  # optional
MATERIALS_DIRS=["/materials/1","/materials/2"]
```

## Endpoints

- `POST /v1/podcasts` → create job (see root README for payload)
- `GET  /v1/podcasts/{id}` → status
- `GET  /v1/podcasts?status=done` → list finished
- `DELETE /v1/podcasts/{id}` → cancel/remove
- `GET  /v1/podcasts/_debug/{id}` → raw state (debug)
- Static: `/media/audio/<id>.mp3`

## Implementation notes

The materials directory should be placed in the project root (same level as backend and frontend folders).

- **Script generation**: OpenAI (if key present) or deterministic local builder.
- **Materials detection**: prefers content‑pillar JSON; else reads PDF/MD/TXT/JSON and composes source text.
- **TTS**: gTTS wrapper with cleaning of labels/URLs to avoid spelling out noise.
- **State**: in‑memory store for demo purposes.

## Customize

- Swap `app/services/tts_service.py` with your preferred TTS engine.
- Extend `app/services/openai_service.py` to add your models/prompts.
- Add new adapters for other input shapes.
