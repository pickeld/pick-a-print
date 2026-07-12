from fastapi import APIRouter

router = APIRouter(prefix="/uploads", tags=["uploads"])

# Uploads are handled via POST /jobs/ with multipart files.
# This router is reserved for presigned MinIO URLs in a future version.

@router.get("/health")
async def uploads_health() -> dict:
    return {"status": "ok"}
