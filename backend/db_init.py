import json
import logging
import os
import time

from app import db_pool, init_db


def run_init():
    logger = logging.getLogger("steam-roulette-db-init")
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    max_retries = int(os.environ.get("DB_INIT_MAX_RETRIES", "30"))
    retry_delay = int(os.environ.get("DB_INIT_RETRY_DELAY_SECONDS", "2"))

    if not db_pool:
        logger.error(json.dumps({
            "event": "db_init_failed",
            "reason": "DATABASE_URL not configured"
        }))
        return 1

    for attempt in range(1, max_retries + 1):
        try:
            ok = init_db()
            if not ok:
                raise RuntimeError("init_db returned unsuccessful status")
            logger.info(json.dumps({"event": "db_init_completed", "attempt": attempt}))
            return 0
        except Exception as exc:
            logger.warning(json.dumps({
                "event": "db_init_retry",
                "attempt": attempt,
                "error": str(exc),
            }))
            time.sleep(retry_delay)

    logger.error(json.dumps({
        "event": "db_init_failed",
        "reason": "exhausted retries",
        "max_retries": max_retries,
    }))
    return 1


if __name__ == "__main__":
    raise SystemExit(run_init())
