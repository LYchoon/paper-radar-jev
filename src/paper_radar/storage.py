"""Atomic files and a recoverable JSONL source of truth."""
import json
import os
import tempfile
from datetime import date
from pathlib import Path

from pydantic import TypeAdapter

from .evaluator import checked_probability
from .models import EvaluatedPaper


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_seen(path: Path) -> set[str]:
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, list) or any(not isinstance(x, str) for x in data):
        raise ValueError(f"Invalid seen file: {path}")
    return set(data)


def save_seen(path: Path, seen: set[str]) -> None:
    atomic_write(path, json.dumps(sorted(seen), ensure_ascii=False, indent=2) + "\n")


def load_database(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    ids = set()
    adapter = TypeAdapter(EvaluatedPaper)
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            record = json.loads(line)
            paper = adapter.validate_python(record)
            checked_probability(paper.relevance_score)
            for score in paper.dimension_scores.values():
                checked_probability(score)
            if not isinstance(record["date"], str) or not isinstance(record["profile_key"], str):
                raise ValueError("Invalid record metadata")
            if date.fromisoformat(record["date"]).isoformat() != record["date"]:
                raise ValueError("Invalid record date")
            if paper.id in ids:
                raise ValueError("Duplicate database ID")
            ids.add(paper.id)
            records.append(record)
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError(f"Invalid database record at {path}:{line_number}") from exc
    return records


def save_database(path: Path, records: list[dict]) -> None:
    # An atomic rewrite preserves JSONL format and avoids partial trailing lines.
    # This deliberately trades append speed for safe recovery at MVP scale.
    atomic_write(path, "".join(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n"
                              for r in records))
