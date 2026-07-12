from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache


def _env_flag(name: str) -> bool | None:
    value = os.getenv(name, "").strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    return None


@lru_cache(maxsize=1)
def colmap_cuda_available() -> bool:
    """True when COLMAP dense stereo (CUDA) is available in this container."""
    override = _env_flag("COLMAP_USE_GPU")
    if override is not None:
        return override

    if shutil.which("nvidia-smi"):
        try:
            proc = subprocess.run(
                ["nvidia-smi", "-L"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if proc.returncode == 0 and "GPU" in (proc.stdout or ""):
                pass  # GPU present; still verify COLMAP CUDA build below
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    colmap = shutil.which("colmap")
    if not colmap:
        return False

    try:
        proc = subprocess.run(
            [colmap, "patch_match_stereo", "-h"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

    combined = f"{proc.stdout}\n{proc.stderr}".lower()
    if "requires cuda" in combined and "not available" in combined:
        return False
    return proc.returncode == 0


@lru_cache(maxsize=1)
def openmvs_available() -> bool:
    return bool(shutil.which("InterfaceCOLMAP") and shutil.which("ReconstructMesh"))
