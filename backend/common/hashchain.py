import hashlib
import json


def compute_hash(prev_hash: str, payload: dict) -> str:
    """Tamper-evident hash chain for append-only logs (D-011)."""
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(f"{prev_hash}|{body}".encode()).hexdigest()
