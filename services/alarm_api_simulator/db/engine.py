"""Engine construction for the alarmdb connection (alarmapi_rw only -- see D-05)."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine


def build_dsn(*, host: str, port: int, user: str, password: str, database: str) -> str:
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"


def create_alarmdb_engine(dsn: str) -> Engine:
    return create_engine(dsn, pool_pre_ping=True)
