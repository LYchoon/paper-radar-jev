import json
from dataclasses import asdict, replace

from paper_radar.models import EvaluatedPaper
from paper_radar.report import build_report, render_markdown, save_daily_report, sort_papers


def evaluated(paper, score):
    return EvaluatedPaper(**asdict(paper), relevance_score=score, relevant=score >= 0.5)


def test_sort_filter_limit_and_statistics(config, paper):
    papers = [evaluated(paper, score) for score in [0.1, 0.9, 0.6]]
    assert [p.relevance_score for p in sort_papers(papers, config)] == [0.9, 0.6, 0.1]
    config.output.max_papers_in_report = 1
    report = build_report(papers, config, "2026-09-20")
    assert report["statistics"] == {"evaluated": 3, "relevant": 2, "shown": 1}
    assert report["papers"][0]["priority"] == "high"
    config.output.include_irrelevant = True
    config.output.max_papers_in_report = 50
    config.output.sort_order = "ascending"
    report = build_report(papers, config, "2026-09-20")
    assert [p["relevance_score"] for p in report["papers"]] == [0.1, 0.6, 0.9]


def test_markdown_and_json(tmp_path, config, paper):
    result = evaluated(paper, 0.9)
    markdown = render_markdown(build_report([result], config, "2026-09-20"))
    for value in ["Visual synthesis", "0.9000", "Alice", "image synthesis", paper.url]:
        assert value in markdown
    paths = save_daily_report([result], config, "2026-09-20", tmp_path)
    assert {p.suffix for p in paths} == {".md", ".json"}
    assert all(p.exists() for p in paths)


def test_empty_report(config):
    assert "No papers match" in render_markdown(build_report([], config, "2026-09-20"))


def test_json_preserves_all_results_while_markdown_filters(tmp_path, config, paper):
    config.output.include_irrelevant = False
    config.output.max_papers_in_report = 1
    papers = [
        evaluated(replace(paper, id="2609.00001", title="Low score paper"), 0.123456789),
        evaluated(replace(paper, id="2609.00002", title="High score paper"), 0.912345678),
        evaluated(replace(paper, id="2609.00003", title="Medium score paper"), 0.6),
    ]
    papers[0].dimension_scores = {"custom": 0.234567891}
    paths = save_daily_report(papers, config, "2026-09-20", tmp_path)
    assert set(paths) == {tmp_path / "md/2026-09-20.md", tmp_path / "json/2026-09-20.json"}
    report = json.loads((tmp_path / "json/2026-09-20.json").read_text(encoding="utf-8"))
    assert report["statistics"] == {"evaluated": 3, "relevant": 2, "shown": 3}
    assert [p["id"] for p in report["papers"]] == ["2609.00002", "2609.00003", "2609.00001"]
    low = report["papers"][-1]
    assert low["relevant"] is False
    assert low["relevance_score"] == 0.123456789
    assert low["dimension_scores"] == {"custom": 0.234567891}
    for key, value in asdict(papers[0]).items():
        assert low[key] == value
    markdown = (tmp_path / "md/2026-09-20.md").read_text(encoding="utf-8")
    assert "High score paper" in markdown
    assert "Medium score paper" not in markdown
    assert "Low score paper" not in markdown


def test_all_irrelevant_retained_in_json(tmp_path, config, paper):
    save_daily_report([evaluated(paper, 0.1)], config, "2026-09-20", tmp_path)
    report = json.loads((tmp_path / "json/2026-09-20.json").read_text(encoding="utf-8"))
    assert len(report["papers"]) == 1
    assert report["papers"][0]["relevant"] is False
    assert "No papers match" in (tmp_path / "md/2026-09-20.md").read_text(encoding="utf-8")
