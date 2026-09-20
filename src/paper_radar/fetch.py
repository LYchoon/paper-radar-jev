import re
from urllib.parse import parse_qs, urlparse

from .config import Config
from .models import Paper


class ArxivFetchError(RuntimeError):
    """A source failure with safe, actionable diagnostics."""


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
    client = client or arxiv.Client(page_size=min(100, settings.max_results), delay_seconds=3, num_retries=3)
    papers = {}
    try:
        for result in client.results(search):
            paper_id = normalize_arxiv_id(result.entry_id)
            papers.setdefault(paper_id, Paper(
                id=paper_id, title=" ".join(result.title.split()),
                abstract=result.summary.strip(), authors=[a.name for a in result.authors],
                categories=list(result.categories), published=result.published.isoformat(),
                updated=result.updated.isoformat() if result.updated else None,
                url=result.entry_id,
            ))
    except arxiv.HTTPError as exc:
        query = parse_qs(urlparse(exc.url).query)
        # Report pagination metadata, never the full URL or request body.
        offset = query.get("start", ["unknown"])[0]
        offset = offset if offset.isdigit() else "unknown"
        if exc.status == 429:
            hint = "Rate limited; wait before running again."
        elif exc.status >= 500:
            hint = "arXiv or an upstream gateway returned a server error; try again later."
        elif exc.status == 403:
            hint = "Request was forbidden; check network/proxy restrictions."
        else:
            hint = "Check the arXiv query and network response."
        raise ArxivFetchError(
            f"arXiv HTTP {exc.status} at start={offset} after {exc.retry} retries. "
            f"Fetched {len(papers)} unique papers before failure; evaluation has not started. "
            f"{hint} TypeSafe credentials are not used for this request."
        ) from exc
    except arxiv.UnexpectedEmptyPageError as exc:
        raise ArxivFetchError(
            f"arXiv returned an unexpected empty page after {exc.retry} retries. "
            "Evaluation has not started; try again later."
        ) from exc
    return list(papers.values())
