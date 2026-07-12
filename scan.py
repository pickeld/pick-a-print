#!/usr/bin/env python3
"""CLI entry point — run photogrammetry pipeline locally."""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import uuid
from pathlib import Path

from app.models.enums import JobStage
from app.models.job import Job
from app.pipeline.config import PipelineConfig
from app.pipeline.orchestrator import ReconstructionPipeline
from app.storage.local import LocalStorage


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Photogrammetry scan-to-STL pipeline")
    parser.add_argument("--input", "-i", required=True, type=Path, help="Input images directory or video file")
    parser.add_argument("--output", "-o", required=True, type=Path, help="Output directory for final artifacts")
    parser.add_argument("--job-id", type=str, default=None, help="Job ID (auto-generated if omitted)")
    parser.add_argument("--workspace", type=Path, default=Path("./data/jobs"), help="Job workspace root")
    parser.add_argument("--from-stage", type=str, default=None, choices=[s.value for s in JobStage])
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser.parse_args()


def prepare_input(storage: LocalStorage, job_id: str, input_path: Path) -> None:
    ws = storage.workspace(job_id)
    ws.ensure_dirs()

    if input_path.is_dir():
        storage.save_inputs_from_dir(job_id, input_path)
    elif input_path.is_file():
        storage.save_input(job_id, input_path)
    else:
        raise SystemExit(f"Input not found: {input_path}")


def copy_outputs(ws_root: Path, output_dir: Path) -> None:
    src = ws_root / "output"
    if not src.exists():
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        if f.is_file():
            shutil.copy2(f, output_dir / f.name)


def main() -> int:
    args = parse_args()
    setup_logging(args.verbose)

    job_id = args.job_id or str(uuid.uuid4())
    config = PipelineConfig(workspace_root=args.workspace)

    storage = LocalStorage(config.workspace_root)
    prepare_input(storage, job_id, args.input)

    job = Job.create(job_id)
    job.save(config.workspace_root)

    from_stage = JobStage(args.from_stage) if args.from_stage else None
    pipeline = ReconstructionPipeline(job_id, config)

    try:
        result = pipeline.run(from_stage=from_stage)
    except Exception as exc:
        logging.error("Pipeline failed: %s", exc)
        return 1

    copy_outputs(storage.workspace(job_id).root, args.output)

    if result.stage == JobStage.COMPLETED:
        logging.info("Done. Outputs in %s", args.output)
        for name in ("model.ply", "model.obj", "model.glb", "model.stl", "report.json"):
            path = args.output / name
            if path.exists():
                logging.info("  %s (%d bytes)", name, path.stat().st_size)
        return 0

    logging.error("Pipeline ended in stage %s: %s", result.stage, result.error)
    return 1


if __name__ == "__main__":
    sys.exit(main())
