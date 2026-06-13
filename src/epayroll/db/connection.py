from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

import psycopg2
import psycopg2.extensions


DEFAULT_URL = "postgresql://epayroll:epayroll@localhost:5432/epayroll"


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_URL)


@contextmanager
def get_connection(url: str | None = None) -> Generator[psycopg2.extensions.connection, None, None]:
    conn = psycopg2.connect(url or get_database_url())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
