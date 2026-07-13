import re
from pathlib import PurePath

from django.contrib import messages
from django.shortcuts import redirect

from library.scan_services import ScanError, create_scan_job
from library.services import ModelSaveError, save_model_from_upload, save_model_from_url

SCAN_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif",
    ".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v", ".zip",
}
MODEL_EXTENSIONS = {".stl", ".3mf"}
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)


def extract_url(*texts: str) -> str | None:
    for text in texts:
        if not text:
            continue
        match = URL_RE.search(text.strip())
        if match:
            return match.group(0)
    return None


def classify_upload(filename: str, content_type: str = "") -> str | None:
    ext = PurePath(filename).suffix.lower()
    if ext in MODEL_EXTENSIONS:
        return "model"
    if ext in SCAN_EXTENSIONS:
        return "scan"
    if content_type.startswith("image/") or content_type.startswith("video/"):
        return "scan"
    if content_type == "application/zip":
        return "scan"
    return None


def process_share_import(request, *, title: str, text: str, url: str, files):
    share_url = url or extract_url(text, title)

    scan_files = []
    model_files = []
    for uploaded in files:
        kind = classify_upload(uploaded.name, uploaded.content_type or "")
        if kind == "model":
            model_files.append(uploaded)
        elif kind == "scan":
            scan_files.append(uploaded)

    last_model = None
    for uploaded in model_files:
        last_model = save_model_from_upload(
            user=request.user,
            uploaded_file=uploaded,
            title=title or None,
        )
    if last_model:
        messages.success(request, f'"{last_model.title}" uploaded from share.')
        return redirect("model_detail", pk=last_model.pk)

    if scan_files:
        scan_job = create_scan_job(
            user=request.user,
            files=scan_files,
            title=title or None,
        )
        messages.success(request, "Scan started from shared files.")
        return redirect("scan_job", job_id=scan_job.job_id)

    if share_url:
        model = save_model_from_url(user=request.user, url=share_url)
        verb = "saved" if getattr(model, "_was_created", True) else "updated"
        messages.success(request, f'"{model.title}" {verb} from shared link.')
        return redirect("model_detail", pk=model.pk)

    messages.warning(request, "Nothing to import from share.")
    return redirect("home")
