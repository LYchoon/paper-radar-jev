import hashlib
import json
import logging
from contextlib import nullcontext
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from filelock import FileLock
from pydantic import TypeAdapter

from .config import Config, load_config, project_root, storage_paths
from .evaluator import create_client, evaluate_paper
from .fetch import fetch_latest_papers
from .models import EvaluatedPaper
from .report import save_daily_report
from .storage import load_database, load_seen, save_database, save_seen

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    fetched: int
    evaluated: int
    failed: int
    reports: list[Path]


def profile_key(config: Config) -> str:
    # Filtering changes must never silently reuse another profile's seen set.
    payload = {"research": config.research.model_dump(),
               "evaluation": config.evaluation.model_dump(),
               "profile": config.profile.model_dump()}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def run_pipeline(config_path: str | Path, *, fetcher=None, client=None,
                 today: date | None = None) -> RunResult:
    config_path = Path(config_path)
    config = load_config(config_path)
    seen_path, database_path, daily_dir = storage_paths(config, config_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    # Lock all shared resources, even when two configs share only one of them.
    locks = sorted({str(database_path) + ".lock", str(seen_path) + ".lock",
                    str(daily_dir / ".paper-radar.lock")})
    from contextlib import ExitStack
    with ExitStack() as stack:
        for path in locks:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            stack.enter_context(FileLock(path, timeout=0))
        records = load_database(database_path)
        key = profile_key(config)
        if any(r["profile_key"] != key for r in records):
            raise ValueError("Research/evaluation profile changed. Use separate storage paths "
                             "or archive and reset both seen.json and papers.jsonl.")
        seen = load_seen(seen_path)
        persisted_ids = {r["id"] for r in records}
        if seen - persisted_ids:
            raise ValueError("seen.json contains IDs missing from papers.jsonl; restore the "
                             "database or archive both files before restarting.")
        # Recovers from an interruption after database commit but before seen save.
        seen.update(persisted_ids)
        logger.info("Fetching latest arXiv papers")
        papers = (fetcher or fetch_latest_papers)(config)
        new = {paper.id: paper for paper in papers if paper.id not in seen}
        logger.info("Fetched %d papers; %d new", len(papers), len(new))
        day = (today or date.today()).isoformat()
        failed = 0
        succeeded = 0
        manager = nullcontext(client)
        if new and client is None:
            manager = create_client(env_file=project_root(config_path) / ".env")
        with manager as active_client:
            for index, paper in enumerate(new.values(), 1):
                logger.info("[%d/%d] %s", index, len(new), paper.id)
                try:
                    result = evaluate_paper(active_client, paper, config)
                except Exception as exc:
                    # Do not log provider bodies or research content.
                    logger.error("Evaluation failed for %s (%s); will retry next run",
                                 paper.id, type(exc).__name__)
                    failed += 1
                    continue
                # Storage errors must abort: never mislabel failed persistence as an API error.
                record = {"date": day, "profile_key": key, **asdict(result)}
                save_database(database_path, [*records, record])
                records.append(record)
                seen.add(paper.id)
                succeeded += 1
                logger.info("%s relevance=%.4f", paper.id, result.relevance_score)
        # Regenerate every recorded day to recover interrupted report writes,
        # preserving same-day results even when this invocation finds no new papers.
        adapter = TypeAdapter(EvaluatedPaper)
        days = sorted({r["date"] for r in records} | {day})
        reports = []
        for report_day in days:
            daily_papers = [adapter.validate_python(r) for r in records
                            if r["date"] == report_day]
            paths = save_daily_report(daily_papers, config, report_day, daily_dir)
            if report_day == day:
                reports = paths
        save_seen(seen_path, seen)
        for path in reports:
            logger.info("Generated %s", path)
        return RunResult(len(papers), succeeded, failed, reports)
