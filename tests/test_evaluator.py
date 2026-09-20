from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import typesafe_sdk

from paper_radar.evaluator import build_questions, checked_probability, create_client, evaluate_paper


def test_threshold_inclusive_and_minimal_state(config, paper, client):
    client.system_one.return_value.nouls["relevant"].noul = 0.5
    result = evaluate_paper(client, paper, config)
    assert result.relevant is True
    assert result.relevance_score == 0.5
    state = client.system_one.call_args.kwargs["state"]
    assert set(state) == {"research_profile", "paper"}
    assert "storage" not in state
    assert set(state["paper"]) == {"title", "abstract", "categories"}


def test_dimensions(config, paper, client):
    config.evaluation.dimensions.enabled = True
    config.evaluation.dimensions.questions = {"custom": "Relevant to robotics?"}
    client.system_one.return_value.nouls["custom"] = SimpleNamespace(noul=0.75)
    result = evaluate_paper(client, paper, config)
    assert result.dimension_scores == {"custom": 0.75}
    assert set(build_questions(config)) == {"relevant", "custom"}


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.1, 1.1, True, "0.9", None])
def test_invalid_probabilities(value):
    with pytest.raises(ValueError):
        checked_probability(value)


def test_empty_abstract_never_calls_api(config, paper, client):
    paper.abstract = " "
    with pytest.raises(ValueError):
        evaluate_paper(client, paper, config)
    client.system_one.assert_not_called()


def test_missing_answer(config, paper, client):
    client.system_one.return_value.nouls = {}
    with pytest.raises(KeyError):
        evaluate_paper(client, paper, config)


def test_missing_key(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="TYPESAFE_API_KEY"):
        create_client()


def test_sdk_retry_policy(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-only")
    factory = Mock()
    monkeypatch.setattr(typesafe_sdk, "TypeSafeClient", factory)
    create_client()
    policy = factory.call_args.kwargs["retry"]
    assert policy.max_retries == 3
    assert policy.timeout == 60.0
    assert policy.backoff_max == 4.0
