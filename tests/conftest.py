import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from paper_radar.config import Config
from paper_radar.models import Paper


@pytest.fixture
def raw_config():
    data = json.loads((Path(__file__).parents[1] / "config/config.example.json").read_text(encoding="utf-8"))
    data["evaluation"]["dimensions"] = {"enabled": False, "questions": {}}
    return data


@pytest.fixture
def config(raw_config):
    return Config.model_validate(raw_config)


@pytest.fixture
def config_path(tmp_path, raw_config):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw_config), encoding="utf-8")
    return path


@pytest.fixture
def paper():
    return Paper(id="2609.12345", title="Visual synthesis", abstract="A new image synthesis method.",
                 authors=["Alice", "Bob"], categories=["cs.CV"], published="2026-09-20T00:00:00+00:00",
                 updated=None, url="https://arxiv.org/abs/2609.12345v1")


@pytest.fixture
def client():
    mock = Mock()
    mock.system_one.return_value = SimpleNamespace(nouls={"relevant": SimpleNamespace(noul=0.9)})
    return mock
