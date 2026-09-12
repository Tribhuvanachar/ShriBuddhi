"""Network layer. Only ever exercised on GitHub Actions / Colab -- the Cowork
sandbox has no scraping egress, which is why every parser is testable from
fixtures without touching this module."""
from __future__ import annotations

import hashlib
import os
import time
import urllib.error
import urllib.request

from .common import log

UA = ("DGE-kavya-importer/2.0 (+https://github.com/Tribhuvanachar/bhumandala; "
      "non-commercial, educational)")
CACHE = os.environ.get("KAVYA_CACHE", ".kavya_cache")


class FetchError(RuntimeError):
    pass


def _cache_path(url):
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]
    return os.path.join(CACHE, h)


def get_bytes(url, retries=3, delay=1.0, timeout=300, use_cache=True):
    """Same contract as get(), for an archive rather than a document.

    Ambuda publishes its whole library as one 7.7 MB TEI zip rather than a
    file per text, so a run that imports six of its works should fetch that
    once and read six members out of it.
    """
    cp = _cache_path(url) + ".bin"
    if use_cache and os.path.exists(cp):
        with open(cp, "rb") as fh:
            return fh.read()
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
            if use_cache:
                os.makedirs(CACHE, exist_ok=True)
                with open(cp, "wb") as fh:
                    fh.write(raw)
            return raw
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            last = exc
            log("  fetch failed (%d/%d) %s -- %s" % (attempt + 1, retries, url, exc))
            time.sleep(delay * (attempt + 2))
    raise FetchError("%s: %s" % (url, last))


def get(url, retries=3, delay=1.0, timeout=60, use_cache=True):
    cp = _cache_path(url)
    if use_cache and os.path.exists(cp):
        with open(cp, "rb") as fh:
            return fh.read().decode("utf-8", "replace")
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
            if use_cache:
                os.makedirs(CACHE, exist_ok=True)
                with open(cp, "wb") as fh:
                    fh.write(raw)
            time.sleep(delay)
            return raw.decode("utf-8", "replace")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            last = exc
            log("  fetch failed (%d/%d) %s -- %s" % (attempt + 1, retries, url, exc))
            time.sleep(delay * (attempt + 2))
    raise FetchError("%s: %s" % (url, last))
