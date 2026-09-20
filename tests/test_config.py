import json

import pytest
from pydantic import ValidationError

from paper_radar.config import Config, load_config, storage_paths


def test_config_loads_bom(tmp_path, raw_config):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw_config), encoding="utf-8-sig")
    assert load_config(path).sources.arxiv.max_results == 100


@pytest.mark.parametrize("section,field,value", [
    ("evaluation", "relevance_threshold", 3.5),
    ("evaluation", "relevance_threshold", float("nan")),
    ("evaluation", "high_priority_threshold", 0.1),
    ("sources", "arxiv", {"categories": []}),
    ("research", "summary", "  "),
    ("output", "sort_by", "title"),
    ("output", "max_papers_in_report", 0),
    ("output", "max_papers_in_report", True),
])
def test_invalid_config(raw_config, section, field, value):
    raw_config[section][field] = value
    with pytest.raises(ValidationError):
        Config.model_validate(raw_config)


def test_missing_field(raw_config):
    del raw_config["research"]
    with pytest.raises(ValidationError):
        Config.model_validate(raw_config)


def test_typo_rejected(raw_config):
    raw_config["evaluation"]["relevnce_threshold"] = 0.1
    with pytest.raises(ValidationError):
        Config.model_validate(raw_config)


def test_malformed_json(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(path)


def test_reserved_dimension(raw_config):
    raw_config["evaluation"]["dimensions"] = {"enabled": True, "questions": {"relevant": "Override?"}}
    with pytest.raises(ValidationError):
        Config.model_validate(raw_config)


def test_paths_independent_of_cwd(tmp_path, config):
    seen, db, daily = storage_paths(config, tmp_path / "config/config.json")
    assert seen == tmp_path / "data/seen.json"
    assert db == tmp_path / "data/papers.jsonl"
    assert daily == tmp_path / "daily"
