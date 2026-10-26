"""Bounded, single-flight logo cache with private disposable disk persistence."""
import base64
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import tempfile
from threading import Lock
import time

from backend.app.branding.discovery import LogoAsset, discover_logo
from backend.app.branding.transport import PublicFetcher

POSITIVE_TTL = 7 * 86400
NEGATIVE_TTL = 6 * 3600
MAX_ENTRIES = 512


class LogoBusy(Exception):
    pass


class LogoCache:
    def __init__(self, *, fetch=None, directory=None, clock=time.time):
        self.fetch = fetch if fetch is not None else PublicFetcher()
        self.directory = Path(directory) if directory else Path(tempfile.gettempdir()) / "ace-company-logo-cache-v1"
        self.clock = clock
        self.entries = OrderedDict()
        self.pending = {}
        self.lock = Lock()
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="company-logo")

    def request(self, seed) -> Future:
        key = seed.identity
        with self.lock:
            entry = self.entries.get(key)
            if entry and entry[0] > self.clock():
                self.entries.move_to_end(key)
                ready = Future()
                ready.set_result(entry[1])
                return ready
            if key in self.pending:
                return self.pending[key]
            if len(self.pending) >= 32:
                raise LogoBusy()
            future = self.pool.submit(self._resolve, seed)
            self.pending[key] = future
        def finished(_):
            with self.lock:
                self.pending.pop(key, None)
        future.add_done_callback(finished)
        return future

    def _resolve(self, seed):
        found = self._read(seed.identity)
        if found is None:
            asset = discover_logo(seed, self.fetch)
            expires = self.clock() + (POSITIVE_TTL if asset else NEGATIVE_TTL)
            self._write(seed.identity, expires, asset)
        else:
            expires, asset = found
        with self.lock:
            self.entries[seed.identity] = (expires, asset)
            self.entries.move_to_end(seed.identity)
            while len(self.entries) > MAX_ENTRIES:
                self.entries.popitem(last=False)
        return asset

    def _read(self, key):
        try:
            path = self.directory / f"{key}.json"
            if path.stat().st_size > 100_000:
                return None
            data = json.loads(path.read_text())
            if data["expires"] <= self.clock():
                return None
            if data["asset"] is None:
                return data["expires"], None
            item = data["asset"]
            png = base64.b64decode(item["png"], validate=True)
            if not png.startswith(b"\x89PNG\r\n\x1a\n") or hashlib.sha256(png).hexdigest() != item["sha256"]:
                return None
            return data["expires"], LogoAsset(png, item["source"], item["evidence"], item["fetched_at"])
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def _write(self, key, expires, asset):
        temporary = None
        try:
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            record = {"expires": expires, "asset": None if asset is None else {
                "png": base64.b64encode(asset.png).decode("ascii"),
                "sha256": hashlib.sha256(asset.png).hexdigest(),
                "source": asset.source, "evidence": asset.evidence, "fetched_at": asset.fetched_at,
            }}
            with tempfile.NamedTemporaryFile(mode="w", dir=self.directory, prefix=".logo-", delete=False) as file:
                temporary = file.name
                json.dump(record, file)
            os.replace(temporary, self.directory / f"{key}.json")
            # Evict only this service's disposable cache, never ACE records.
            paths = sorted(self.directory.glob("*.json"), key=lambda p: p.stat().st_mtime)
            for path in paths[:-MAX_ENTRIES]:
                path.unlink(missing_ok=True)
        except OSError:
            pass  # A read-only/full cache directory must not break the website.
        finally:
            if temporary:
                try:
                    Path(temporary).unlink(missing_ok=True)
                except OSError:
                    pass
