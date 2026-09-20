from datetime import datetime, timezone
from types import SimpleNamespace

import arxiv
import pytest

from paper_radar.fetch import build_query, fetch_latest_papers, normalize_arxiv_id


@pytest.mark.parametrize("value,expected", [
    ("2609.12345v1", "2609.12345"),
    ("2609.12345v7", "2609.12345"),
    ("https://arxiv.org/abs/2609.12345v2", "2609.12345"),
    ("https://arxiv.org/pdf/2609.12345v1.pdf", "2609.12345"),
    ("https://arxiv.org/abs/hep-th/9901001v3", "hep-th/9901001"),
])
def test_normalize(value, expected):
    assert normalize_arxiv_id(value) == expected


def test_bad_id():
    with pytest.raises(ValueError):
        normalize_arxiv_id("https://example.org/abs/2609.12345")


def test_query():
    assert build_query(["cs.CV", "cs.LG"]) == "cat:cs.CV OR cat:cs.LG"


def test_fetch_metadata_and_deduplication(config):
    now = datetime(2026, 9, 20, tzinfo=timezone.utc)
    row = SimpleNamespace(entry_id="https://arxiv.org/abs/2609.12345v1",
                          title=" A\n Title ", summary=" abstract ",
                          authors=[SimpleNamespace(name="Alice")], categories=["cs.CV"],
                          published=now, updated=now)

    class FakeClient:
        def results(self, search):
            assert search.max_results == 300
            assert search.sort_by == arxiv.SortCriterion.SubmittedDate
            assert search.sort_order == arxiv.SortOrder.Descending
            return [row, row]

    results = fetch_latest_papers(config, FakeClient())
    assert len(results) == 1
    assert results[0].id == "2609.12345"
    assert results[0].title == "A Title"
    assert results[0].abstract == "abstract"
    assert results[0].authors == ["Alice"]


def test_disabled(config):
    config.sources.arxiv.enabled = False
    assert fetch_latest_papers(config) == []
