"""Structured logging helpers."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager


def new_flow_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def log_event(event: str, **fields) -> None:
    payload = " ".join([f"{k}={v}" for k, v in fields.items() if v is not None])
    logging.info(f"{event} {payload}".strip())


@contextmanager
def timed(event: str, **fields):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        log_event(event, elapsed_ms=elapsed_ms, **fields)
