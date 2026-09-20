import argparse
import logging
from pathlib import Path

from .config import load_config, storage_paths
from .pipeline import run_pipeline
from .fetch import ArxivFetchError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rank new arXiv papers using TypeSafe AI.")
    parser.add_argument("--config", type=Path, default=Path("config/config.json"))
    parser.add_argument("--check-config", action="store_true", help="Validate config without network calls")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # SDK debug mode may include research data, so keep ordinary CLI logs concise.
    logging.getLogger("typesafe_sdk").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        if args.check_config:
            config = load_config(args.config)
            storage_paths(config, args.config)
            logging.info("Valid configuration: %s", config.profile.name)
            return 0
        result = run_pipeline(args.config)
        logging.info("Finished: %d evaluated, %d failed", result.evaluated, result.failed)
        return 2 if result.failed else 0
    except ArxivFetchError as exc:
        logging.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        logging.error("Interrupted; persisted evaluations will be recovered on the next run")
        return 130
    except Exception as exc:
        # Config errors are safe to explain; provider errors may carry request content.
        if isinstance(exc, (ValueError, FileNotFoundError)):
            # Pydantic's str() includes input values, so suppress them.
            from pydantic import ValidationError
            if isinstance(exc, ValidationError):
                for issue in exc.errors(include_input=False, include_url=False):
                    logging.error("Config %s: %s", ".".join(map(str, issue["loc"])), issue["msg"])
            else:
                logging.error("%s", exc)
        else:
            logging.error("Run failed (%s). Check network, credentials, file permissions, "
                          "or whether another run holds the storage lock.", type(exc).__name__)
        return 1
