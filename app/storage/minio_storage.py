from __future__ import annotations

import os
from pathlib import Path

from app.storage.local import LocalStorage


class MinioStorage(LocalStorage):
    """S3-compatible storage via MinIO for remote scan workers."""

    def __init__(self, root: Path, endpoint: str, access_key: str, secret_key: str, bucket: str) -> None:
        super().__init__(root)
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket = bucket
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from minio import Minio
        except ImportError as exc:
            raise RuntimeError(
                "MINIO_ENDPOINT is set but the minio package is not installed"
            ) from exc

        self._client = Minio(
            self.endpoint.replace("http://", "").replace("https://", ""),
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.endpoint.startswith("https"),
        )
        if not self._client.bucket_exists(self.bucket):
            self._client.make_bucket(self.bucket)
        return self._client

    def upload_file(self, local_path: Path, object_key: str) -> None:
        client = self._get_client()
        client.fput_object(self.bucket, object_key, str(local_path))

    def download_prefix(self, job_id: str, local_ws: Path) -> None:
        client = self._get_client()
        prefix = f"jobs/{job_id}/"
        local_ws.mkdir(parents=True, exist_ok=True)
        for obj in client.list_objects(self.bucket, prefix=prefix, recursive=True):
            rel = obj.object_name[len(prefix) :]
            if not rel:
                continue
            dest = local_ws / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            client.fget_object(self.bucket, obj.object_name, str(dest))

    def upload_workspace(self, job_id: str, ws_root: Path) -> None:
        """Upload inputs and job state so a remote GPU worker can process the scan."""
        client = self._get_client()
        ws_root = Path(ws_root)
        candidates: list[Path] = []
        job_json = ws_root / "job.json"
        if job_json.exists():
            candidates.append(job_json)
        input_dir = ws_root / "input"
        if input_dir.exists():
            candidates.extend(p for p in input_dir.rglob("*") if p.is_file())
        for path in candidates:
            rel = path.relative_to(ws_root)
            key = f"jobs/{job_id}/{rel.as_posix()}"
            client.fput_object(self.bucket, key, str(path))

    def push_job_state(self, job_id: str, ws_root: Path) -> None:
        """Upload pipeline state and outputs after remote processing."""
        client = self._get_client()
        ws_root = Path(ws_root)
        paths: list[Path] = []
        job_json = ws_root / "job.json"
        if job_json.exists():
            paths.append(job_json)
        output_dir = ws_root / "output"
        if output_dir.exists():
            paths.extend(p for p in output_dir.rglob("*") if p.is_file())
        for path in paths:
            rel = path.relative_to(ws_root)
            key = f"jobs/{job_id}/{rel.as_posix()}"
            client.fput_object(self.bucket, key, str(path))

    def pull_job_state(self, job_id: str, ws_root: Path) -> None:
        """Refresh local job.json and outputs from object storage."""
        client = self._get_client()
        ws_root = Path(ws_root)
        ws_root.mkdir(parents=True, exist_ok=True)
        prefixes = (f"jobs/{job_id}/job.json", f"jobs/{job_id}/output/")
        for prefix in prefixes:
            for obj in client.list_objects(self.bucket, prefix=prefix, recursive=True):
                rel = obj.object_name.removeprefix(f"jobs/{job_id}/")
                if not rel:
                    continue
                dest = ws_root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                client.fget_object(self.bucket, obj.object_name, str(dest))

    def sync_outputs(self, job_id: str, output_dir: Path) -> None:
        client = self._get_client()
        for path in output_dir.rglob("*"):
            if path.is_file():
                key = f"jobs/{job_id}/output/{path.relative_to(output_dir)}"
                client.fput_object(self.bucket, key, str(path))


def get_storage() -> LocalStorage | MinioStorage:
    endpoint = os.getenv("MINIO_ENDPOINT")
    if endpoint:
        return MinioStorage(
            root=Path(os.getenv("PIPELINE_DATA_DIR", "./data/jobs")),
            endpoint=endpoint,
            access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
            bucket=os.getenv("MINIO_BUCKET", "scans"),
        )
    return LocalStorage(Path(os.getenv("PIPELINE_DATA_DIR", "./data/jobs")))
