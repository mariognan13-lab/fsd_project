from datetime import datetime, timezone

from .errors import AppError

_client = None
_db = None


def connect(uri):
    global _client, _db
    if not uri:
        return {"connected": False, "reason": "MONGODB_URI is not set. Saved places are unavailable. Live map data does not need MongoDB."}
    try:
        from pymongo import MongoClient
        from pymongo.errors import PyMongoError
    except ImportError:
        return {"connected": False, "reason": "MongoDB connection failed. Saved places are unavailable."}
    try:
        _client = MongoClient(uri, serverSelectionTimeoutMS=2500)
        _client.admin.command("ping")
        _db = _client.get_default_database()
        _db["data_source_status"].create_index([("provider", 1), ("role", 1)], unique=True)
        _db["saved_places"].create_index([("coordinates", "2dsphere")])
        return {"connected": True}
    except Exception:
        _client = None
        _db = None
        return {"connected": False, "reason": "MongoDB connection failed. Saved places are unavailable."}


def connected():
    return _db is not None


def require_db():
    if not connected():
        raise AppError(
            "MongoDB is not connected. The map and live layers do not need it. Set MONGODB_URI to save places or corridors.",
            status=503,
            code="PERSISTENCE_UNAVAILABLE",
        )


def persist_status(record):
    if not connected():
        return
    when = lambda value: datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
    _db["data_source_status"].update_one(
        {"provider": record["provider"], "role": record["role"]},
        {"$set": {
            **record,
            "lastAttemptAt": when(record.get("lastAttemptAt")),
            "lastSuccessAt": when(record.get("lastSuccessAt")),
            "updatedAt": datetime.now(timezone.utc),
        }},
        upsert=True,
    )


def persist_snapshots(features, payload):
    if not connected():
        return {"persisted": 0}
    docs = []
    fetched = datetime.fromisoformat(payload["fetchedAt"].replace("Z", "+00:00"))
    observed = None
    if payload.get("observedAt"):
        observed = datetime.fromisoformat(payload["observedAt"].replace("Z", "+00:00"))
    for feature in features[:200]:
        docs.append({
            "segmentKey": feature["id"],
            "observedAt": observed,
            "fetchedAt": fetched,
            "speed": feature.get("observedSpeed"),
            "freeFlowSpeed": feature.get("freeFlowSpeed"),
            "delay": feature.get("delay"),
            "congestionLevel": feature.get("congestionLevel"),
            "observationBasis": feature.get("observationBasis"),
            "provider": feature.get("provider"),
        })
    if docs:
        _db["traffic_snapshots"].insert_many(docs, ordered=False)
    return {"persisted": len(docs)}


def places():
    require_db()
    return _db["saved_places"]


def corridors():
    require_db()
    return _db["saved_corridors"]
