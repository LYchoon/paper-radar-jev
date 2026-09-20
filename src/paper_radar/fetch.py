import re
from urllib.parse import urlparse

from .config import Config
from .models import Paper


def normalize_arxiv_id(entry_id: str) -> str:
    raw = entry_id.strip()
    if "://" in raw:
        parsed = urlparse(raw)
        if parsed.hostname not in {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}:
            raise ValueError("not an arXiv URL")
        raw = re.sub(r"^/(abs|pdf)/", "", parsed.path).rstrip("/")
    raw = re.sub(r"\.pdf$", "", raw)
    raw = re.sub(r"v\d+$", "", raw)
    if not re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-zA-Z.-]+/\d{7})", raw):
        raise ValueError(f"invalid arXiv identifier: {entry_id}")
    return raw


def build_query(categories: list[str]) -> str:
    return " OR ".join(f"cat:{category}" for category in categories)


def fetch_latest_papers(config: Config, client=None) -> list[Paper]:
    if not config.sources.arxiv.enabled:
        return []
    import arxiv

    settings = config.sources.arxiv
    search = arxiv.Search(
        query=build_query(settings.categories), max_results=settings.max_results,
        sort_by={
            "submitted_date": arxiv.SortCriterion.SubmittedDate,
            "last_updated_date": arxiv.SortCriterion.LastUpdatedDate,
            "relevance": arxiv.SortCriterion.Relevance,
        }[settings.sort_by],
        sort_order={"descending": arxiv.SortOrder.Descending,
                    "ascending": arxiv.SortOrder.Ascending}[settings.sort_order],
    )
    client = client or arxiv.Client(page_size=100, delay_seconds=3, num_retries=3)
    papers = {}
    for result in client.results(search):
        paper_id = normalize_arxiv_id(result.entry_id)
        papers.setdefault(paper_id, Paper(
            id=paper_id, title=" ".join(result.title.split()),
            abstract=result.summary.strip(), authors=[a.name for a in result.authors],
            categories=list(result.categories), published=result.published.isoformat(),
            updated=result.updated.isoformat() if result.updated else None,
            url=result.entry_id,
        ))
    return list(papers.values())
