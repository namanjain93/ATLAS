"""Append-only, hash-chained SQLite event store with snapshots.

* Rows in ``events`` cannot be updated or deleted (SQLite triggers abort).
* Each row's hash = sha256(canonical body incl. prev_hash), so any out-of-band edit
  breaks the chain and is detected by ``verify_chain``.
* ``idempotency_key`` is UNIQUE: re-submitting the same key returns the original event.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from atlas.config.loader import canonical_json
from atlas.events.model import EventType, NewEvent, Priority, StoredEvent
from atlas.runtime.clock import Clock

GENESIS_HASH = "0" * 64

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq             INTEGER PRIMARY KEY,
    event_id        TEXT NOT NULL UNIQUE,
    idempotency_key TEXT UNIQUE,
    type            TEXT NOT NULL,
    priority        TEXT NOT NULL,
    ts_utc          TEXT NOT NULL,
    payload         TEXT NOT NULL,
    config_version  TEXT NOT NULL,
    config_hash     TEXT NOT NULL,
    atlas_version   TEXT NOT NULL,
    prev_hash       TEXT NOT NULL,
    hash            TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
BEGIN SELECT RAISE(ABORT, 'events are immutable'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
BEGIN SELECT RAISE(ABORT, 'events are immutable'); END;
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_seq    INTEGER NOT NULL,
    ts_utc       TEXT NOT NULL,
    state        TEXT NOT NULL,
    state_hash   TEXT NOT NULL
);
"""


class StoreError(Exception):
    pass


@dataclass(frozen=True)
class AppendResult:
    event: StoredEvent
    duplicate: bool


@dataclass(frozen=True)
class ChainReport:
    ok: bool
    events_checked: int
    broken_at_seq: int | None = None
    detail: str = ""


@dataclass(frozen=True)
class Snapshot:
    event_seq: int
    ts_utc: str
    state: dict[str, Any]
    state_hash: str


def state_hash(state: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(state).encode()).hexdigest()


def _event_hash(body: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(body).encode()).hexdigest()


def _body(
    seq: int,
    event_id: str,
    idem: str | None,
    etype: str,
    priority: str,
    ts: str,
    payload_json: str,
    cfg_v: str,
    cfg_h: str,
    atlas_v: str,
    prev: str,
) -> dict[str, Any]:
    return {
        "seq": seq,
        "event_id": event_id,
        "idempotency_key": idem,
        "type": etype,
        "priority": priority,
        "ts_utc": ts,
        "payload": payload_json,
        "config_version": cfg_v,
        "config_hash": cfg_h,
        "atlas_version": atlas_v,
        "prev_hash": prev,
    }


class EventStore:
    def __init__(self, path: Path | str, clock: Clock, atlas_version: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._atlas_version = atlas_version
        self._config_version = "UNSET"
        self._config_hash = "UNSET"
        self._conn = sqlite3.connect(self.path, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.executescript(_SCHEMA)

    # ------------------------------------------------------------------ context
    def set_config_context(self, version: str, fingerprint: str) -> None:
        self._config_version = version
        self._config_hash = fingerprint

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------ writes
    def append(self, new: NewEvent) -> AppendResult:
        payload_json = canonical_json(new.payload)
        cur = self._conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        try:
            if new.idempotency_key is not None:
                row = cur.execute(
                    "SELECT * FROM events WHERE idempotency_key = ?", (new.idempotency_key,)
                ).fetchone()
                if row is not None:
                    cur.execute("COMMIT")
                    return AppendResult(self._row_to_event(row), duplicate=True)
            last = cur.execute("SELECT seq, hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
            seq = (last[0] + 1) if last else 1
            prev = last[1] if last else GENESIS_HASH
            event_id = str(uuid.uuid4())
            ts = self._clock.now_utc().isoformat()
            prio = new.effective_priority.value
            body = _body(
                seq,
                event_id,
                new.idempotency_key,
                new.type.value,
                prio,
                ts,
                payload_json,
                self._config_version,
                self._config_hash,
                self._atlas_version,
                prev,
            )
            h = _event_hash(body)
            cur.execute(
                "INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    seq,
                    event_id,
                    new.idempotency_key,
                    new.type.value,
                    prio,
                    ts,
                    payload_json,
                    self._config_version,
                    self._config_hash,
                    self._atlas_version,
                    prev,
                    h,
                ),
            )
            cur.execute("COMMIT")
        except Exception:
            cur.execute("ROLLBACK")
            raise
        return AppendResult(
            StoredEvent(
                seq,
                event_id,
                new.idempotency_key,
                new.type,
                Priority(prio),
                ts,
                json.loads(payload_json),
                self._config_version,
                self._config_hash,
                self._atlas_version,
                prev,
                h,
            ),
            duplicate=False,
        )

    def write_snapshot(self, event_seq: int, state: dict[str, Any]) -> Snapshot:
        ts = self._clock.now_utc().isoformat()
        sh = state_hash(state)
        self._conn.execute(
            "INSERT INTO snapshots (event_seq, ts_utc, state, state_hash) VALUES (?,?,?,?)",
            (event_seq, ts, canonical_json(state), sh),
        )
        return Snapshot(event_seq, ts, state, sh)

    # ------------------------------------------------------------------ reads
    def _row_to_event(self, row: tuple) -> StoredEvent:
        (seq, eid, idem, etype, prio, ts, payload, cv, ch, av, prev, h) = row
        return StoredEvent(
            seq, eid, idem, EventType(etype), Priority(prio), ts, json.loads(payload), cv, ch, av, prev, h
        )

    def iter_events(self, upto_seq: int | None = None) -> Iterator[StoredEvent]:
        q = "SELECT * FROM events"
        args: tuple = ()
        if upto_seq is not None:
            q += " WHERE seq <= ?"
            args = (upto_seq,)
        for row in self._conn.execute(q + " ORDER BY seq", args):
            yield self._row_to_event(row)

    def get_by_idempotency_key(self, key: str) -> StoredEvent | None:
        row = self._conn.execute("SELECT * FROM events WHERE idempotency_key = ?", (key,)).fetchone()
        return self._row_to_event(row) if row else None

    def tail(self, n: int) -> list[StoredEvent]:
        rows = self._conn.execute("SELECT * FROM events ORDER BY seq DESC LIMIT ?", (n,)).fetchall()
        return [self._row_to_event(r) for r in reversed(rows)]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    def latest_snapshot(self) -> Snapshot | None:
        row = self._conn.execute(
            "SELECT event_seq, ts_utc, state, state_hash FROM snapshots ORDER BY snapshot_seq DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return Snapshot(row[0], row[1], json.loads(row[2]), row[3])

    def verify_chain(self) -> ChainReport:
        prev = GENESIS_HASH
        expected_seq = 1
        n = 0
        for row in self._conn.execute("SELECT * FROM events ORDER BY seq"):
            (seq, eid, idem, etype, prio, ts, payload, cv, ch, av, prev_h, h) = row
            n += 1
            if seq != expected_seq:
                return ChainReport(False, n, seq, f"sequence gap: expected {expected_seq}, found {seq}")
            if prev_h != prev:
                return ChainReport(False, n, seq, "prev_hash does not match previous event hash")
            recomputed = _event_hash(_body(seq, eid, idem, etype, prio, ts, payload, cv, ch, av, prev_h))
            if recomputed != h:
                return ChainReport(False, n, seq, "event content does not match its hash (tampered)")
            prev = h
            expected_seq += 1
        return ChainReport(True, n)
