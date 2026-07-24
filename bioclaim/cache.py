"""Transparent, persistent on-disk cache for database lookups.

Every existence / entity lookup is cached to disk, so:
  - repeat lookups are instant,
  - a warmed cache works fully offline,
  - rate limits stop mattering (each id is fetched at most once, ever).

Only *definitive* results are cached (a real answer from the database). Transient
failures (network/None) are never cached, so a hiccup can't poison the cache.

Cache location: $BIOCLAIM_CACHE, else ~/.cache/bioclaim/. Disable with
BIOCLAIM_CACHE=off.
"""
import os
import json
import atexit
import pathlib
import threading


def _cache_dir():
    override = os.environ.get("BIOCLAIM_CACHE")
    if override and override.lower() == "off":
        return None
    base = pathlib.Path(override) if override else pathlib.Path.home() / ".cache" / "bioclaim"
    try:
        base.mkdir(parents=True, exist_ok=True)
        return base
    except Exception:
        return None


class DiskCache:
    """A tiny JSON-backed dict with atomic, batched persistence."""

    def __init__(self, name):
        self._dir = _cache_dir()
        self._path = (self._dir / f"{name}.json") if self._dir else None
        self._lock = threading.Lock()
        self._data = {}
        self._writes = 0
        if self._path and self._path.exists():
            try:
                self._data = json.loads(self._path.read_text())
            except Exception:
                self._data = {}
        atexit.register(self.flush)

    _MISS = object()

    def get(self, key):
        return self._data.get(key, DiskCache._MISS)

    def set(self, key, value):
        with self._lock:
            self._data[key] = value
            self._writes += 1
            due = self._writes % 25 == 0
        if due:
            self.flush()

    def flush(self):
        if not self._path:
            return
        with self._lock:
            try:
                tmp = self._path.with_suffix(".tmp")
                tmp.write_text(json.dumps(self._data))
                tmp.replace(self._path)
            except Exception:
                pass

    def __len__(self):
        return len(self._data)


MISS = DiskCache._MISS
