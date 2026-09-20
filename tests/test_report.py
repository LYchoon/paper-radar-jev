from dataclasses import asdict

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
