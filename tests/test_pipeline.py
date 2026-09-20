import json
from dataclasses import replace
from datetime import date
from unittest.mock import Mock

import pytest

import paper_radar.pipeline as pipeline
from paper_radar.storage import load_database, load_seen


DAY = date(2026, 9, 20)


def test_partial_failure_and_same_day_rerun(config_path, paper, client):
    broken = replace(paper, id="2609.12346", abstract="")
    fetcher = lambda _: [paper, broken, paper]
    first = pipeline.run_pipeline(config_path, fetcher=fetcher, client=client, today=DAY)
    assert (first.evaluated, first.failed) == (1, 1)
    assert load_seen(config_path.parent / "data/seen.json") == {paper.id}
    second = pipeline.run_pipeline(config_path, fetcher=fetcher, client=client, today=DAY)
    assert (second.evaluated, second.failed) == (0, 1)
    client.system_one.assert_called_once()
    report = json.loads((config_path.parent / "daily/2026-09-20.json").read_text(encoding="utf-8"))
    assert report["statistics"]["evaluated"] == 1
    assert len(load_database(config_path.parent / "data/papers.jsonl")) == 1


def test_provider_failure_continues(config_path, paper, client):
    other = replace(paper, id="2609.12346")
    response = client.system_one.return_value
    client.system_one.side_effect = [TimeoutError(), response]
    result = pipeline.run_pipeline(config_path, fetcher=lambda _: [paper, other],
                                   client=client, today=DAY)
    assert result.failed == result.evaluated == 1
    assert load_seen(config_path.parent / "data/seen.json") == {other.id}


def test_report_failure_recovers_without_reevaluation(config_path, paper, client, monkeypatch):
    original = pipeline.save_daily_report
    monkeypatch.setattr(pipeline, "save_daily_report", Mock(side_effect=OSError("disk")))
    with pytest.raises(OSError):
        pipeline.run_pipeline(config_path, fetcher=lambda _: [paper], client=client, today=DAY)
    assert not (config_path.parent / "data/seen.json").exists()
    monkeypatch.setattr(pipeline, "save_daily_report", original)
    pipeline.run_pipeline(config_path, fetcher=lambda _: [paper], client=client,
                          today=date(2026, 9, 21))
    client.system_one.assert_called_once()
    assert (config_path.parent / "daily/2026-09-20.md").exists()
    assert load_seen(config_path.parent / "data/seen.json") == {paper.id}


def test_storage_failure_does_not_mark_seen(config_path, paper, client, monkeypatch):
    monkeypatch.setattr(pipeline, "save_database", Mock(side_effect=OSError("disk")))
    with pytest.raises(OSError):
        pipeline.run_pipeline(config_path, fetcher=lambda _: [paper], client=client, today=DAY)
    assert not (config_path.parent / "data/seen.json").exists()


def test_profile_change_requires_separate_storage(config_path, paper, client):
    pipeline.run_pipeline(config_path, fetcher=lambda _: [paper], client=client, today=DAY)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["research"]["summary"] = "Robotics"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="profile changed"):
        pipeline.run_pipeline(config_path, fetcher=lambda _: [], client=client, today=DAY)


def test_fetch_failure_does_not_create_seen(config_path, client):
    with pytest.raises(TimeoutError):
        pipeline.run_pipeline(config_path, fetcher=Mock(side_effect=TimeoutError()),
                              client=client, today=DAY)
    assert not (config_path.parent / "data/seen.json").exists()


def test_empty_run_needs_no_api_key(config_path, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    result = pipeline.run_pipeline(config_path, fetcher=lambda _: [], today=DAY)
    assert result.evaluated == result.failed == 0
