from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EngineResult:
    ok: bool
    message: str = ""
    outputs: list[Path] | None = None


def run_command(cmd: list[str], cwd: Path | None = None, timeout: int | None = None) -> EngineResult:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return EngineResult(False, f"Command not found: {cmd[0]}")
    except subprocess.TimeoutExpired:
        return EngineResult(False, f"Command timed out: {' '.join(cmd)}")

    if proc.returncode != 0:
        stderr = (proc.stderr or proc.stdout or "").strip()[-2000:]
        return EngineResult(False, f"Exit {proc.returncode}: {stderr}")

    return EngineResult(True, "ok")


def require_binary(name: str) -> str | None:
    return shutil.which(name)
