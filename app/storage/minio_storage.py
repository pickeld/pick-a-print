from __future__ import annotations

import os
from pathlib import Path

from app.storage.local import LocalStorage


class MinioStorage(LocalStorage):
    """S3-compatible storage via MinIO. Falls back to local paths when boto3/minio unavailable."""

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

            self._client = Minio(
                self.endpoint.replace("http://", "").replace("https://", ""),
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.endpoint.startswith("https"),
            )
            if not self._client.bucket_exists(self.bucket):
                self._client.make_bucket(self.bucket)
            return self._client
        except ImportError:
            return None

    def upload_file(self, local_path: Path, object_key: str) -> None:
        client = self._get_client()
        if client is None:
            return
        client.fput_object(self.bucket, object_key, str(local_path))

    def download_prefix(self, job_id: str, local_ws: Path) -> None:
        client = self._get_client()
        if client is None:
            return
        prefix = f"jobs/{job_id}/"
        for obj in client.list_objects(self.bucket, prefix=prefix, recursive=True):
            rel = obj.object_name[len(prefix) :]
            dest = local_ws / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            client.fget_object(self.bucket, obj.object_name, str(dest))

    def sync_outputs(self, job_id: str, output_dir: Path) -> None:
        client = self._get_client()
        if client is None:
            return
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
