"""Document store abstraction: in-memory (local/demo) or Firestore (cloud).

Documents are plain JSON-serialisable dicts. Collections are flat names such as
`ts_assessments` (no sub-collections) to keep both backends identical.
"""
from __future__ import annotations

import copy
import threading
import uuid
from typing import Any, Iterable

from ..config import settings


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


class MemoryStore:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, dict]] = {}
        self._lock = threading.RLock()

    def get(self, coll: str, doc_id: str) -> dict | None:
        with self._lock:
            d = self._data.get(coll, {}).get(doc_id)
            return copy.deepcopy(d) if d is not None else None

    def set(self, coll: str, doc_id: str, data: dict) -> None:
        with self._lock:
            self._data.setdefault(coll, {})[doc_id] = copy.deepcopy(data)

    def update(self, coll: str, doc_id: str, fields: dict) -> None:
        with self._lock:
            doc = self._data.setdefault(coll, {}).setdefault(doc_id, {})
            doc.update(copy.deepcopy(fields))

    def delete(self, coll: str, doc_id: str) -> None:
        with self._lock:
            self._data.get(coll, {}).pop(doc_id, None)

    def list(self, coll: str, where: dict[str, Any] | None = None, order_by: str | None = None,
             desc: bool = False, limit: int | None = None) -> list[dict]:
        with self._lock:
            docs = [copy.deepcopy(d) for d in self._data.get(coll, {}).values()]
        if where:
            docs = [d for d in docs if all(d.get(k) == v for k, v in where.items())]
        if order_by:
            docs.sort(key=lambda d: (d.get(order_by) is None, d.get(order_by)), reverse=desc)
        return docs[:limit] if limit else docs

    def count(self, coll: str) -> int:
        with self._lock:
            return len(self._data.get(coll, {}))

    def clear(self, colls: Iterable[str]) -> None:
        with self._lock:
            for c in colls:
                self._data.pop(c, None)


class FirestoreStore:
    def __init__(self) -> None:
        from google.cloud import firestore

        self._fs = firestore
        self._db = firestore.Client(project=settings.project, database=settings.firestore_db)

    def get(self, coll: str, doc_id: str) -> dict | None:
        snap = self._db.collection(coll).document(doc_id).get()
        return snap.to_dict() if snap.exists else None

    def set(self, coll: str, doc_id: str, data: dict) -> None:
        self._db.collection(coll).document(doc_id).set(data)

    def update(self, coll: str, doc_id: str, fields: dict) -> None:
        self._db.collection(coll).document(doc_id).set(fields, merge=True)

    def delete(self, coll: str, doc_id: str) -> None:
        self._db.collection(coll).document(doc_id).delete()

    def list(self, coll: str, where: dict[str, Any] | None = None, order_by: str | None = None,
             desc: bool = False, limit: int | None = None) -> list[dict]:
        q = self._db.collection(coll)
        for k, v in (where or {}).items():
            q = q.where(filter=self._fs.FieldFilter(k, "==", v))
        if order_by and not where:  # avoid needing composite indexes; sort client-side otherwise
            q = q.order_by(order_by, direction=self._fs.Query.DESCENDING if desc else self._fs.Query.ASCENDING)
            if limit:
                q = q.limit(limit)
            return [s.to_dict() for s in q.stream()]
        docs = [s.to_dict() for s in q.stream()]
        if order_by:
            docs.sort(key=lambda d: (d.get(order_by) is None, d.get(order_by)), reverse=desc)
        return docs[:limit] if limit else docs

    def count(self, coll: str) -> int:
        return self._db.collection(coll).count().get()[0][0].value

    def clear(self, colls: Iterable[str]) -> None:
        for c in colls:
            batch, n = self._db.batch(), 0
            for snap in self._db.collection(c).list_documents():
                batch.delete(snap)
                n += 1
                if n % 400 == 0:
                    batch.commit()
                    batch = self._db.batch()
            batch.commit()


_store: MemoryStore | FirestoreStore | None = None


def store() -> MemoryStore | FirestoreStore:
    global _store
    if _store is None:
        _store = FirestoreStore() if settings.store_backend == "firestore" else MemoryStore()
    return _store
