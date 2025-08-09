from fastapi import FastAPI
from app.api.v1.podcast import router as podcast_router

app = FastAPI()
app.include_router(podcast_router)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/test")
def test(name: str):
    return {"message": f"Hello {name}"}
