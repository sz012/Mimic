from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from engine.schema import Assignment, Campaign, Evidence, Feature, Item

DEFAULT_PATH = "data/cache/mimic.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    paths TEXT NOT NULL,
    features TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    members TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assignments (
    item_id TEXT PRIMARY KEY,
    campaign_id TEXT,
    score REAL NOT NULL,
    evidence TEXT NOT NULL
);
"""


def default_path() -> Path:
    return Path(os.environ.get("MIMIC_DB_PATH") or DEFAULT_PATH)


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _item_from_row(row: tuple) -> Item:
    item_id, case_id, paths, features = row
    return Item(
        id=item_id,
        case_id=case_id,
        paths=json.loads(paths),
        features={name: Feature(**data) for name, data in json.loads(features).items()},
    )


class Store:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def upsert_item(self, item: Item) -> None:
        features = {name: asdict(feature) for name, feature in item.features.items()}
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO items (id, case_id, paths, features) VALUES (?, ?, ?, ?)",
                (item.id, item.case_id, _dump(item.paths), _dump(features)),
            )

    def items(self) -> list[Item]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id, case_id, paths, features FROM items ORDER BY id")
            return [_item_from_row(row) for row in rows.fetchall()]

    def get_item(self, item_id: str) -> Item | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, case_id, paths, features FROM items WHERE id = ?", (item_id,)
            ).fetchone()
        return _item_from_row(row) if row else None

    def save_campaigns(self, campaigns: list[Campaign]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM campaigns")
            conn.executemany(
                "INSERT INTO campaigns (id, members) VALUES (?, ?)",
                [(c.id, _dump(c.members)) for c in campaigns],
            )

    def campaigns(self) -> list[Campaign]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id, members FROM campaigns ORDER BY id").fetchall()
        return [Campaign(id=cid, members=json.loads(members)) for cid, members in rows]

    def save_assignment(self, assignment: Assignment) -> None:
        evidence = [asdict(e) for e in assignment.evidence]
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO assignments (item_id, campaign_id, score, evidence)"
                " VALUES (?, ?, ?, ?)",
                (assignment.item_id, assignment.campaign_id, assignment.score, _dump(evidence)),
            )

    def assignments(self) -> list[Assignment]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT item_id, campaign_id, score, evidence FROM assignments ORDER BY item_id"
            ).fetchall()
        return [
            Assignment(
                item_id=item_id,
                campaign_id=campaign_id,
                score=score,
                evidence=[Evidence(**e) for e in json.loads(evidence)],
            )
            for item_id, campaign_id, score, evidence in rows
        ]

    def clear(self) -> None:
        with self._connect() as conn:
            for table in ("items", "campaigns", "assignments"):
                conn.execute(f"DELETE FROM {table}")


def load_items() -> list[Item]:
    path = default_path()
    if not path.exists():
        return []
    return Store(path).items()
