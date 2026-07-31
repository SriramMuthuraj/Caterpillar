"""In-memory stand-in for MongoDB, loaded from the seed files.

Why this exists: the API is unusable without Atlas — every route 500s — and the
demo has to survive no network, a shared password nobody can find, and a cluster
that is asleep. Falling back to the seed files means the app always comes up
with a full fleet; only durability is lost, and writes still work for the life
of the process.

This is deliberately **not** a Mongo emulator. It implements exactly the surface
the four services in ``Cat_SRTS/backend/services/`` actually call:

    find(filter, projection) -> cursor with .sort(key, direction) and .limit(n)
    find_one(filter)
    find_one_and_update(filter, {"$set": ...}, return_document=...)
    insert_one(document)          -> result.inserted_id
    delete_one(filter)            -> result.deleted_count
    count_documents(filter, limit=...)
    aggregate(pipeline)           -> $match, $sort, $group, $limit

Query operators: exact equality, ``$in``, ``$or``, ``$gt``, ``$gte``, ``$lt``,
``$lte``, ``$ne``. Anything else raises rather than silently matching nothing —
a filter that quietly returns everything is a worse failure than a crash.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from bson import ObjectId

BASE_DIR = Path(__file__).resolve().parent

SEED_FILES = {
    "equipment": "equipment_seed.json",
    "operators": "operators_seed.json",
    "assignments": "assignments_seed.json",
    "usage_logs": "usage_logs_seed.json",
}


def _from_extended_json(value: Any) -> Any:
    """Convert Mongo Extended JSON to native types.

    Duplicated from seed.py rather than imported: seed.py imports database.py,
    which imports this module, and the cycle would not resolve.
    """
    if isinstance(value, list):
        return [_from_extended_json(item) for item in value]
    if isinstance(value, dict):
        if set(value.keys()) == {"$oid"}:
            return ObjectId(value["$oid"])
        if set(value.keys()) == {"$date"}:
            raw = value["$date"]
            if isinstance(raw, dict) and "$numberLong" in raw:
                return datetime.fromtimestamp(int(raw["$numberLong"]) / 1000)
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return {key: _from_extended_json(item) for key, item in value.items()}
    return value


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------

def _compare(value: Any, operator: str, operand: Any) -> bool:
    if operator == "$in":
        return value in operand
    if operator == "$nin":
        return value not in operand
    if operator == "$ne":
        return value != operand
    if value is None:
        # Mongo does not order None against a number; neither do we.
        return False
    try:
        if operator == "$gt":
            return value > operand
        if operator == "$gte":
            return value >= operand
        if operator == "$lt":
            return value < operand
        if operator == "$lte":
            return value <= operand
    except TypeError:
        return False
    raise NotImplementedError(
        f"memory_store does not implement the {operator} operator"
    )


def _matches(document: dict, query: dict | None) -> bool:
    if not query:
        return True

    for key, condition in query.items():
        if key == "$or":
            if not any(_matches(document, clause) for clause in condition):
                return False
            continue
        if key == "$and":
            if not all(_matches(document, clause) for clause in condition):
                return False
            continue

        value = document.get(key)
        if isinstance(condition, dict) and condition \
                and all(k.startswith("$") for k in condition):
            for operator, operand in condition.items():
                if not _compare(value, operator, operand):
                    return False
        elif value != condition:
            return False

    return True


def _project(document: dict, projection: dict | None) -> dict:
    if not projection:
        return document
    # Only inclusion projections are used ({"field": 1}); _id rides along unless
    # explicitly excluded, matching Mongo's behaviour.
    keep = {key for key, flag in projection.items() if flag}
    if projection.get("_id", 1):
        keep.add("_id")
    return {key: value for key, value in document.items() if key in keep}


# --------------------------------------------------------------------------
# Cursor
# --------------------------------------------------------------------------

class MemoryCursor:
    """Lazy-ish cursor supporting the chained .sort().limit() the services use."""

    def __init__(self, documents: list[dict]):
        self._documents = documents

    def sort(self, key, direction=1):
        self._documents = sorted(
            self._documents,
            key=lambda doc: (doc.get(key) is None, doc.get(key)),
            reverse=direction < 0,
        )
        return self

    def limit(self, count: int):
        if count:
            self._documents = self._documents[:count]
        return self

    def __iter__(self):
        return iter(self._documents)

    def __len__(self):
        return len(self._documents)


class _WriteResult:
    def __init__(self, inserted_id=None, deleted_count=0, modified_count=0):
        self.inserted_id = inserted_id
        self.deleted_count = deleted_count
        self.modified_count = modified_count
        self.matched_count = modified_count


# --------------------------------------------------------------------------
# Collection
# --------------------------------------------------------------------------

class MemoryCollection:

    def __init__(self, name: str, documents: list[dict]):
        self.name = name
        self._documents = documents

    # -- reads ------------------------------------------------------------

    def find(self, filter=None, projection=None) -> MemoryCursor:
        return MemoryCursor([
            _project(copy.deepcopy(doc), projection)
            for doc in self._documents if _matches(doc, filter)
        ])

    def find_one(self, filter=None, projection=None):
        for doc in self._documents:
            if _matches(doc, filter):
                return _project(copy.deepcopy(doc), projection)
        return None

    def count_documents(self, filter=None, limit=0) -> int:
        count = 0
        for doc in self._documents:
            if _matches(doc, filter):
                count += 1
                if limit and count >= limit:
                    break
        return count

    def distinct(self, key: str, filter=None) -> list:
        seen = []
        for doc in self._documents:
            if _matches(doc, filter) and doc.get(key) not in seen:
                seen.append(doc.get(key))
        return seen

    # -- writes -----------------------------------------------------------

    def insert_one(self, document: dict) -> _WriteResult:
        document = copy.deepcopy(document)
        document.setdefault("_id", ObjectId())
        self._documents.append(document)
        return _WriteResult(inserted_id=document["_id"])

    def insert_many(self, documents) -> _WriteResult:
        for document in documents:
            self.insert_one(document)
        return _WriteResult()

    def update_one(self, filter, update, **_kwargs) -> _WriteResult:
        for doc in self._documents:
            if _matches(doc, filter):
                doc.update(update.get("$set", {}))
                return _WriteResult(modified_count=1)
        return _WriteResult()

    def find_one_and_update(self, filter, update, return_document=True,
                            **_kwargs):
        for doc in self._documents:
            if _matches(doc, filter):
                before = copy.deepcopy(doc)
                doc.update(update.get("$set", {}))
                return copy.deepcopy(doc) if return_document else before
        return None

    def delete_one(self, filter) -> _WriteResult:
        for index, doc in enumerate(self._documents):
            if _matches(doc, filter):
                self._documents.pop(index)
                return _WriteResult(deleted_count=1)
        return _WriteResult()

    def delete_many(self, filter) -> _WriteResult:
        keep = [d for d in self._documents if not _matches(d, filter)]
        removed = len(self._documents) - len(keep)
        self._documents[:] = keep
        return _WriteResult(deleted_count=removed)

    def create_index(self, *_args, **_kwargs) -> str:
        return "memory_noop"          # nothing to index; scans are the plan

    # -- aggregation ------------------------------------------------------

    def aggregate(self, pipeline) -> list[dict]:
        """Just enough pipeline for the three the services actually run."""
        rows = [copy.deepcopy(doc) for doc in self._documents]

        for stage in pipeline:
            (operator, spec), = stage.items()

            if operator == "$match":
                rows = [row for row in rows if _matches(row, spec)]

            elif operator == "$sort":
                for key, direction in reversed(list(spec.items())):
                    rows.sort(
                        key=lambda r, k=key: (r.get(k) is None, r.get(k)),
                        reverse=direction < 0,
                    )

            elif operator == "$limit":
                rows = rows[:spec]

            elif operator == "$group":
                rows = _group(rows, spec)

            elif operator == "$project":
                rows = [_project(row, spec) for row in rows]

            else:
                raise NotImplementedError(
                    f"memory_store does not implement the {operator} stage"
                )

        return rows


def _group(rows: list[dict], spec: dict) -> list[dict]:
    """$group with $first, $sum and $push — the accumulators in use."""
    key_expr = spec["_id"]
    buckets: dict[Any, list[dict]] = {}
    order: list[Any] = []

    for row in rows:
        key = row.get(key_expr[1:]) if isinstance(key_expr, str) \
            and key_expr.startswith("$") else key_expr
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(row)

    grouped = []
    for key in order:
        members = buckets[key]
        out = {"_id": key}

        for field, accumulator in spec.items():
            if field == "_id":
                continue
            (name, expr), = accumulator.items()

            if name == "$first":
                # "$$ROOT" means the whole document, which is how the latest
                # usage log per machine is picked out.
                out[field] = members[0] if expr == "$$ROOT" \
                    else members[0].get(str(expr).lstrip("$"))
            elif name == "$last":
                out[field] = members[-1] if expr == "$$ROOT" \
                    else members[-1].get(str(expr).lstrip("$"))
            elif name == "$sum":
                if isinstance(expr, (int, float)):
                    out[field] = len(members) * expr
                else:
                    field_name = str(expr).lstrip("$")
                    out[field] = sum(
                        m.get(field_name) or 0 for m in members
                    )
            elif name == "$push":
                out[field] = [
                    m if expr == "$$ROOT" else m.get(str(expr).lstrip("$"))
                    for m in members
                ]
            else:
                raise NotImplementedError(
                    f"memory_store does not implement the {name} accumulator"
                )

        grouped.append(out)

    return grouped


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------

class MemoryDatabase:
    """Dict-of-collections with the same ``db["name"]`` access Mongo gives."""

    name = "smart_rental_tracking_system (in-memory)"

    def __init__(self, collections: dict[str, list[dict]]):
        self._collections = {
            name: MemoryCollection(name, documents)
            for name, documents in collections.items()
        }

    def __getitem__(self, name: str) -> MemoryCollection:
        if name not in self._collections:
            self._collections[name] = MemoryCollection(name, [])
        return self._collections[name]

    def list_collection_names(self) -> list[str]:
        return sorted(self._collections)

    def command(self, *_args, **_kwargs) -> dict:
        return {"ok": 1.0}            # satisfies the health check's ping


def load() -> MemoryDatabase:
    """Build the store from the seed files on disk."""
    collections: dict[str, list[dict]] = {}

    for collection, filename in SEED_FILES.items():
        path = BASE_DIR / filename
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                collections[collection] = _from_extended_json(json.load(handle))
        else:
            collections[collection] = []

    return MemoryDatabase(collections)
