from __future__ import annotations

import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EngineResult:
    ok: bool
    message: str = ""
    outputs: list[Path] | None = None


def run_command(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: int | None = None,
    on_line: Callable[[str], None] | None = None,
) -> EngineResult:
    if on_line is None:
        return _run_command_buffered(cmd, cwd=cwd, timeout=timeout)
    return _run_command_streaming(cmd, cwd=cwd, timeout=timeout, on_line=on_line)


def _run_command_buffered(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: int | None = None,
) -> EngineResult:
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


def _run_command_streaming(
    cmd: list[str],
    *,
    cwd: Path | None,
    timeout: int | None,
    on_line: Callable[[str], None],
) -> EngineResult:
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        return EngineResult(False, f"Command not found: {cmd[0]}")

    output_lines: list[str] = []
    deadline = time.monotonic() + timeout if timeout else None
    assert proc.stdout is not None

    try:
        for line in proc.stdout:
            if deadline is not None and time.monotonic() > deadline:
                proc.kill()
                proc.wait(timeout=30)
                return EngineResult(False, f"Command timed out: {' '.join(cmd)}")
            cleaned = line.rstrip("\n\r")
            output_lines.append(cleaned)
            if cleaned.strip():
                on_line(cleaned)
        returncode = proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=30)
        return EngineResult(False, f"Command timed out: {' '.join(cmd)}")

    if returncode != 0:
        stderr = "\n".join(output_lines).strip()[-2000:]
        return EngineResult(False, f"Exit {returncode}: {stderr}")

    return EngineResult(True, "ok")


def require_binary(name: str) -> str | None:
    return shutil.which(name)
