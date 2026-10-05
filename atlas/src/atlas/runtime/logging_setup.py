"""Structured (JSON-lines) logging."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra = getattr(record, "fields", None)
        if isinstance(extra, dict):
            data.update(extra)
        return json.dumps(data, default=str, ensure_ascii=False)


def get_logger(home: Path) -> logging.Logger:
    logger = logging.getLogger(f"atlas.{home.resolve()}")
    if not logger.handlers:
        (home / "logs").mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(home / "logs" / "atlas.log", encoding="utf-8")
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log(logger: logging.Logger, level: int, msg: str, **fields: object) -> None:
    logger.log(level, msg, extra={"fields": fields})
