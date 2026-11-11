"""Evaluator-only assets, independent of the task's installation directory."""
import hashlib
import json
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent


class ReviewRequired(ValueError):
    """A new artifact needs a local evaluator decision before settlement."""


def source_path():
    candidates = sorted((HERE / "materials").glob("*.xlsx"))
    if len(candidates) != 1 or candidates[0].is_symlink():
        raise ValueError("Expected one evaluator-side source workbook")
    return candidates[0]


def packaged_review(artifact_sha256):
    index = json.loads((HERE / "review_index.json").read_text(encoding="utf-8"))
    if index.get("schema_version") != "ppm-packaged-reviews-v1":
        raise ValueError("Unsupported packaged review index")
    record = index["artifacts"].get(artifact_sha256)
    if record is None:
        raise ReviewRequired("Unreviewed artifact: local evaluator review required; no external judge is called")
    filename = record["file"]
    if filename != artifact_sha256 + ".json" or not re.fullmatch(r"[a-f0-9]{64}\.json", filename):
        raise ValueError("Invalid packaged review path")
    path = HERE / "reviews" / filename
    if path.is_symlink() or not path.is_file():
        raise ValueError("Packaged review missing or symlinked")
    if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
        raise ValueError("Packaged review digest mismatch")
    return path
