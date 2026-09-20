import json
from dataclasses import asdict

import pytest

from paper_radar.models import EvaluatedPaper
from paper_radar.storage import atomic_write, load_database, load_seen, save_database, save_seen


def test_seen_missing_and_roundtrip(tmp_path):
    path = tmp_path / "nested/seen.json"
    assert load_seen(path) == set()
    save_seen(path, {"b", "a"})
    assert load_seen(path) == {"a", "b"}
    path.write_text('["a", "a"]', encoding="utf-8")
    assert load_seen(path) == {"a"}


def test_malformed_seen(tmp_path):
    path = tmp_path / "seen.json"
    path.write_text('{"a": true}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_seen(path)


def test_database_roundtrip(tmp_path, paper):
    path = tmp_path / "papers.jsonl"
    row = {"date": "2026-09-20", "profile_key": "hash",
           **asdict(EvaluatedPaper(**asdict(paper), relevance_score=0.8, relevant=True))}
    save_database(path, [row])
    assert load_database(path) == [row]
    with path.open("a", encoding="utf-8") as stream:
        stream.write('{"partial":')
    with pytest.raises(ValueError, match=":2"):
        load_database(path)


def test_atomic_failure_preserves_original(tmp_path, monkeypatch):
    path = tmp_path / "file.json"
    path.write_text("original", encoding="utf-8")

    def fail(*args):
        raise OSError("disk error")

    monkeypatch.setattr("paper_radar.storage.os.replace", fail)
    with pytest.raises(OSError):
        atomic_write(path, "new")
    assert path.read_text(encoding="utf-8") == "original"
    assert list(tmp_path.iterdir()) == [path]
