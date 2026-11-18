from __future__ import annotations

import json
import os
import re
from pathlib import Path

ARTIFACT_ID = re.compile(r"^[a-f0-9]{32}$")


class ArtifactNotFound(FileNotFoundError):
    pass


def artifact_root() -> Path:
    configured = os.getenv("SKILL_ARTIFACT_DIR", "").strip()
    return Path(configured) if configured else Path(__file__).resolve().parent / "artifacts"


def artifact_path(user_id: int, artifact_id: str) -> tuple[Path, dict]:
    if not ARTIFACT_ID.fullmatch(artifact_id):
        raise ArtifactNotFound(artifact_id)
    directory = artifact_root() / str(int(user_id))
    target = directory / f"{artifact_id}.pptx"
    meta_file = directory / f"{artifact_id}.json"
    if not target.is_file() or not meta_file.is_file():
        raise ArtifactNotFound(artifact_id)
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ArtifactNotFound(artifact_id) from exc
    return target, meta


def load_artifact_source(user_id: int, artifact_id: str) -> dict:
    """Load the editable source of a published, teacher-owned presentation."""
    path, _ = artifact_path(user_id, artifact_id)
    try:
        source = json.loads(path.with_suffix(".source.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ArtifactNotFound(artifact_id) from exc
    if not isinstance(source, dict) or not isinstance(source.get("slides"), list) or not source["slides"]:
        raise ArtifactNotFound(artifact_id)
    return source
