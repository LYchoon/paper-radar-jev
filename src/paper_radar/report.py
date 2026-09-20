import html
import json
import re
from dataclasses import asdict
from pathlib import Path

from .config import Config
from .models import EvaluatedPaper
from .storage import atomic_write


def priority_label(score: float, config: Config) -> str:
    if score >= config.evaluation.high_priority_threshold:
        return "high"
    if score >= config.evaluation.relevance_threshold:
        return "medium"
    return "low"


def sort_papers(papers: list[EvaluatedPaper], config: Config) -> list[EvaluatedPaper]:
    return sorted(papers, key=lambda p: p.relevance_score,
                  reverse=config.output.sort_order == "descending")


def escape_markdown(value: str) -> str:
    value = html.escape(value, quote=False)
    return re.sub(r"([\\\x60*_{}\[\]()#+.!|>~-])", r"\\\1", value)


def build_report(papers: list[EvaluatedPaper], config: Config, day: str) -> dict:
    selected = [p for p in sort_papers(papers, config)
                if config.output.include_irrelevant or p.relevant]
    selected = selected[:config.output.max_papers_in_report]
    return {
        "date": day, "profile": config.profile.name,
        "statistics": {"evaluated": len(papers), "relevant": sum(p.relevant for p in papers),
                       "shown": len(selected)},
        "papers": [{**asdict(p), "priority": priority_label(p.relevance_score, config)}
                   for p in selected],
    }


def render_markdown(report: dict) -> str:
    stats = report["statistics"]
    lines = [f'# Daily Paper Radar â€” {report["date"]}', "",
             f'**Profile:** {escape_markdown(report["profile"])}', "",
             f'New papers evaluated: {stats["evaluated"]}', "",
             f'Relevant papers: {stats["relevant"]}', "",
             f'Papers shown: {stats["shown"]}', ""]
    if not report["papers"]:
        lines += ["No papers match the report filters.", ""]
    for index, paper in enumerate(report["papers"], 1):
        lines += ["---", "", f'## {index}. {escape_markdown(paper["title"])}', "",
                  f'**Relevance:** {paper["relevance_score"]:.4f}', "",
                  f'**Priority:** {paper["priority"].title()}', "",
                  f'**Categories:** {escape_markdown(", ".join(paper["categories"]))}', "",
                  f'**Authors:** {escape_markdown(", ".join(paper["authors"]))}', "",
                  f'**Published:** {escape_markdown(paper["published"])}', "",
                  f'**Updated:** {escape_markdown(paper["updated"] or "â€”")}', "",
                  f'**arXiv:** <{paper["url"]}>', ""]
        if paper["dimension_scores"]:
            lines += ["### Dimension Scores", "", "| Dimension | Score |", "|---|---:|"]
            lines += [f"| {escape_markdown(name)} | {score:.4f} |"
                      for name, score in paper["dimension_scores"].items()]
            lines += [""]
        lines += ["### Abstract", "", escape_markdown(paper["abstract"]), ""]
    return "\n".join(lines)


def save_daily_report(papers: list[EvaluatedPaper], config: Config, day: str,
                      directory: Path) -> list[Path]:
    report = build_report(papers, config, day)
    outputs = []
    if config.output.markdown:
        path = directory / f"{day}.md"
        atomic_write(path, render_markdown(report))
        outputs.append(path)
    if config.output.json_output:
        path = directory / f"{day}.json"
        atomic_write(path, json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        outputs.append(path)
    return outputs
