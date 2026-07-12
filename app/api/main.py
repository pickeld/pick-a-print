from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import jobs, results, uploads

app = FastAPI(title="Photogrammetry API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(uploads.router)
app.include_router(jobs.router)
app.include_router(results.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "photogrammetry-api"}
