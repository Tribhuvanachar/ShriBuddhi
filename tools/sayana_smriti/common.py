"""
common.py — shared HTTP + text + IO helpers for the DGE Sāyaṇa / Smṛti importers.

Design notes (please read before editing):

* Every network call goes through `Fetcher`, which throttles, retries with
  backoff, and caches responses on disk. wisdomlib.org intermittently returns
  403 / read-timeouts under load — the retry + throttle is not optional.
* The on-disk cache (`--cache-dir`, default `.httpcache/`) means a re-run after
  a partial failure costs nothing. In GitHub Actions, wire it to actions/cache
  so a re-run of a 10k-page job resumes instead of restarting.
* Nothing here writes into the DGE tree. Writers live in the importers and are
  additive-merge only: an existing field is never overwritten unless
  --overwrite is passed.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Optional

import requests

USER_AGENT = (
    "DGE-import/1.0 (Digital Grantha Engine; non-commercial educational digital library; "
    "github.com/Tribhuvanachar/bhumandala)"
)

DEFAULT_DELAY = 1.2          # seconds between requests to the same host
DEFAULT_TIMEOUT = 45
DEFAULT_RETRIES = 5


class Fetcher:
    def __init__(self, cache_dir="./.httpcache", delay=DEFAULT_DELAY,
                 timeout=DEFAULT_TIMEOUT, retries=DEFAULT_RETRIES, offline=False):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        self.offline = offline
        self._last = 0.0
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.stats = {"hit": 0, "miss": 0, "fail": 0}

    def _cache_path(self, url: str) -> Path:
        h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
        return self.cache_dir / f"{h}.bin"

    def get(self, url: str, allow_missing=False) -> Optional[str]:
        """Return decoded text for `url`, or None if it 404s / permanently fails."""
        cp = self._cache_path(url)
        if cp.exists():
            self.stats["hit"] += 1
            data = cp.read_bytes()
            return None if data == b"__404__" else data.decode("utf-8", "replace")
        if self.offline:
            if allow_missing:
                return None
            raise RuntimeError(f"offline mode and {url} not in cache")

        last_err = None
        for attempt in range(self.retries):
            now = time.time()
            wait = self.delay - (now - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            try:
                r = self.session.get(url, timeout=self.timeout, allow_redirects=True)
                if r.status_code == 404:
                    cp.write_bytes(b"__404__")
                    self.stats["miss"] += 1
                    return None
                if r.status_code in (403, 429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"HTTP {r.status_code}")
                r.raise_for_status()
                r.encoding = r.encoding or "utf-8"
                text = r.text
                cp.write_bytes(text.encode("utf-8"))
                self.stats["miss"] += 1
                return text
            except Exception as e:               # noqa: BLE001 - deliberate catch-all
                last_err = e
                sleep = (2 ** attempt) + random.random() * 1.5
                print(f"  ! {url} attempt {attempt+1}/{self.retries}: {e} "
                      f"(retry in {sleep:.1f}s)", file=sys.stderr)
                time.sleep(sleep)
        self.stats["fail"] += 1
        if allow_missing:
            return None
        raise RuntimeError(f"failed after {self.retries} attempts: {url} ({last_err})")


# ---------------------------------------------------------------- text utils

_WS = re.compile(r"[ \t ]+")
_NL = re.compile(r"\n{3,}")


def clean(s: str) -> str:
    """Normalise whitespace and Unicode without touching Devanagari/IAST marks."""
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s)
    s = s.replace("​", "").replace("﻿", "")
    s = _WS.sub(" ", s)
    s = _NL.sub("\n\n", s)
    return s.strip()


# Vedic accent sanitiser — mirrors dgeSanitizeVedicAccents() in dge/js/core.js.
# The Vedic Extensions codepoints render as tofu in most fonts; the core
# Devanagari block marks (U+0951/U+0952) have existed since Unicode 1.1.
_VEDIC_FIX = {
    "᳒": "॑",   # VEDIC TONE PRENKHA  -> DEVANAGARI STRESS SIGN UDATTA
    "᳓": "॑",
    "᳚": "॑",
    "᳙": "॒",   # -> DEVANAGARI STRESS SIGN ANUDATTA
    "᳝": "॒",
}


def sanitize_vedic_accents(s: str) -> str:
    if not s:
        return s
    for a, b in _VEDIC_FIX.items():
        s = s.replace(a, b)
    return s


DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def has_devanagari(s: str) -> bool:
    return bool(s and DEVANAGARI.search(s))


def strip_sacred_texts_diacritics(s: str) -> str:
    """sacred-texts.com encodes diacritics as *n*, *s*, ri etc. Unwrap the
    asterisk form so `VISH*N*U` -> `VISHNU` without eating real asterisks."""
    return re.sub(r"\*([A-Za-z])\*", r"\1", s or "")


# ------------------------------------------------------------------ file IO

def load_json(path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def sniff_indent(raw, default=1):
    """The indent width a JSON file is already written at.

    Read off the first indented key rather than assumed. The corpus is not
    uniform -- the Ṛgveda and Sāmaveda saṃhitā files are written at 2 while most
    of this toolchain writes at 1 -- and guessing wrong corrupts nothing but
    reformats every line of a 10,000-item file to add one key per item, burying
    the real change under a quarter of a million whitespace edits.
    """
    for line in raw.split("\n", 40)[1:]:
        stripped = line.lstrip(" ")
        if stripped.startswith('"') and stripped != line:
            return len(line) - len(stripped)
    return default


def save_json(path, obj, indent=None):
    """Atomic write — a killed job never leaves a half-written data.json in the
    tree (which is how you get a grantha that 404s silently in the browser).

    With no ``indent`` given, an existing file keeps the width it already has
    and a new one is written at 1.
    """
    path = Path(path)
    if indent is None:
        try:
            indent = sniff_indent(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            indent = 1
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=indent)
        fh.write("\n")
    os.replace(tmp, path)


def append_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
