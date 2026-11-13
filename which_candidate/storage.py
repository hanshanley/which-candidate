import gzip
import hashlib
import json
from pathlib import Path


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n").encode()


def fingerprint(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"sha256": digest.hexdigest(), "bytes": path.stat().st_size}


def write_json(path, value):
    Path(path).write_bytes(json_bytes(value))


def write_rows(path, rows):
    body = b"".join(json_bytes(row) for row in rows)
    Path(path).write_bytes(gzip.compress(body, mtime=0))


def read_rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def confined(root, relative):
    root = Path(root).resolve()
    result = (root / relative).resolve()
    if not result.is_relative_to(root):
        raise ValueError(f"Path escapes its root: {relative}")
    return result
