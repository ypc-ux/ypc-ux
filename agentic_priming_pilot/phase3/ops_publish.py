"""Best-effort bridge to the ypc-ux/ops digest pipe.

ops isn't a dependency of this project — it's a sibling private repo that
collects state from local projects and emails one portfolio-wide digest
(see ypc-ux/ops/CLAUDE.md). This module locates a local checkout of it via
OPS_REPO_PATH (default: ../ops next to this repo) and calls its
digest.publish.publish(). If ops isn't checked out, or the publish itself
fails, this prints a note and does nothing else — it must never break a
pilot run just because the ops repo isn't present on this machine.
"""
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class LocalSignal:
    """Mirrors ops's digest.schema.Signal without requiring ops to be
    importable just to construct one."""

    project: str
    kind: str  # needs_you | broken | stale | did
    title: str
    detail: str = ""
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    url: str = ""


def _ops_repo_path() -> Path:
    override = os.environ.get("OPS_REPO_PATH")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "ops"


def publish_signals(project: str, signals: list[LocalSignal]) -> bool:
    ops_path = _ops_repo_path()
    if not (ops_path / "digest" / "publish.py").exists():
        print(
            f"[ops_publish] no ops checkout at {ops_path} "
            "(set OPS_REPO_PATH to point at it) — skipping",
            file=sys.stderr,
        )
        return False

    sys.path.insert(0, str(ops_path))
    try:
        from digest.publish import publish  # type: ignore
        from digest.schema import Signal  # type: ignore
    except Exception as exc:  # noqa: BLE001
        print(f"[ops_publish] failed to import ops digest.publish: {exc}", file=sys.stderr)
        return False

    ops_signals = [
        Signal(project=s.project, kind=s.kind, title=s.title, detail=s.detail, ts=s.ts, url=s.url)
        for s in signals
    ]
    return publish(project, ops_signals)
