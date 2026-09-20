from unittest.mock import Mock

from paper_radar.cli import main
from paper_radar.pipeline import RunResult


def test_check_config(config_path):
    assert main(["--config", str(config_path), "--check-config"]) == 0


def test_bad_config(tmp_path):
    assert main(["--config", str(tmp_path / "missing.json")]) == 1


def test_partial_failure_exit_code(monkeypatch, config_path):
    monkeypatch.setattr("paper_radar.cli.run_pipeline", Mock(return_value=RunResult(3, 2, 1, [])))
    assert main(["--config", str(config_path)]) == 2
