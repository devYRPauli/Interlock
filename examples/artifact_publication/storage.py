"""Local reference provider: versioned text artifacts and operator-issued approvals.

The SQLite transaction is the authority for writes. Interlock's journal is separate.
No deletion/retention policy: historical publications must remain queryable.
"""

import contextlib
import hashlib
import json
import math
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterator, Union

from .models import PublicationRejected, PublicationRequest, encode, request


class ArtifactStore:
    """Publish approved text with atomic version checks and retained operation history."""

    def __init__(self, path: Union[str, Path]) -> None:
        self.path = Path(path).resolve()

    @contextlib.contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        # Missing/unavailable storage is an error, never an empty history.
        with (
            contextlib.closing(
                sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=5)
            ) as db,
            db,
        ):
            db.row_factory = sqlite3.Row
            yield db

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.closing(sqlite3.connect(self.path)) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY, payload TEXT NOT NULL,
                    expires REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS publications (
                    reference TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL, version INTEGER NOT NULL,
                    payload TEXT NOT NULL, content TEXT NOT NULL, sha256 TEXT NOT NULL,
                    UNIQUE(name, version)
                );
            """)

    def approve(self, arguments: PublicationRequest, expires: float) -> None:
        """Operator API, deliberately not exposed as an agent tool. Grants are immutable."""
        approved = request(**arguments)
        if (
            type(expires) not in (int, float)
            or not math.isfinite(expires)
            or expires <= time.time()
        ):
            raise PublicationRejected("approval expiry must be a finite future timestamp")
        with self.connect() as db:
            db.execute(
                "INSERT INTO approvals (id, payload, expires) VALUES (?, ?, ?)",
                (approved["approval_id"], encode(approved), expires),
            )

    def revoke(self, approval_id: str) -> None:
        with self.connect() as db:
            if (
                db.execute("UPDATE approvals SET revoked = 1 WHERE id = ?", (approval_id,)).rowcount
                != 1
            ):
                raise PublicationRejected("approval does not exist")

    def get_approval(self, approval_id: str) -> dict[str, Any]:
        with self.connect() as db:
            row = db.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
            if row is None or row["revoked"]:
                return {}
            return {"id": row["id"], "match": json.loads(row["payload"]), "expires": row["expires"]}

    def get_artifact(self, name: str) -> dict[str, Any]:
        with self.connect() as db:
            row = db.execute(
                "SELECT name, version, content, sha256, reference FROM publications "
                "WHERE name = ? ORDER BY version DESC LIMIT 1",
                (name,),
            ).fetchone()
            return (
                dict(row) if row else {"name": name, "version": 0, "content": None, "sha256": None}
            )

    def find_publication(self, reference: str) -> dict[str, Any]:
        with self.connect() as db:
            row = db.execute(
                "SELECT name, version, sha256, reference, request_id FROM publications "
                "WHERE reference = ?",
                (reference,),
            ).fetchone()
            return {"found": row is not None, "publication": dict(row) if row else None}

    def publish_artifact(
        self,
        request_id: str,
        name: str,
        expected_version: int,
        content: str,
        approval_id: str,
        reference: str,
    ) -> dict[str, Any]:
        approved = request(request_id, name, expected_version, content, approval_id)
        if not isinstance(reference, str) or not reference.strip():
            raise PublicationRejected("publication requires an operation reference")
        payload = encode(approved)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute(
                "SELECT * FROM publications WHERE reference = ?", (reference,)
            ).fetchone()
            if previous is not None:
                if previous["payload"] != payload:
                    raise PublicationRejected(
                        "operation reference is already bound to another payload"
                    )
                # A historical success remains a success after revocation or a newer publication.
                return {
                    k: previous[k] for k in ("name", "version", "sha256", "reference", "request_id")
                }
            if db.execute(
                "SELECT 1 FROM publications WHERE request_id = ?", (request_id,)
            ).fetchone():
                raise PublicationRejected(
                    "request_id already published under another operation reference"
                )
            grant = db.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
            if grant is None or grant["revoked"] or grant["expires"] <= time.time():
                raise PublicationRejected("approval is missing, revoked, or expired")
            if grant["payload"] != payload:
                raise PublicationRejected("payload differs from the operator-approved request")
            version = db.execute(
                "SELECT COALESCE(MAX(version), 0) FROM publications WHERE name = ?", (name,)
            ).fetchone()[0]
            if version != expected_version:
                raise PublicationRejected(
                    f"version conflict: expected {expected_version}, current {version}"
                )
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            db.execute(
                "INSERT INTO publications VALUES (?, ?, ?, ?, ?, ?, ?)",
                (reference, request_id, name, version + 1, payload, content, digest),
            )
            return dict(
                name=name,
                version=version + 1,
                sha256=digest,
                reference=reference,
                request_id=request_id,
            )
