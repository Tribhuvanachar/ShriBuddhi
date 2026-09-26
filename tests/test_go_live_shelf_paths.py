"""Every go-live shelf entry must name a directory that exists.

On 26 Sep 2026 the shelf allowed `Tattvavada/Itara/Kavya/mani_manjari`. The
landed grantha is `manimanjari`, with no underscore. Nothing failed, nothing
logged: library.json listed all 8 sargas as populated, the breadcrumb resolved,
and the reader answered "This text is not part of the published library yet."
for all 306 verses. A shelf entry pointing at nothing is indistinguishable
from a text deliberately held back, which is why this has to be a test and
not a habit of checking.
"""
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OVERRIDES = REPO / "admin/config/library-overrides.json"


def shelf():
    return (json.loads(OVERRIDES.read_text(encoding="utf-8")).get("shelf") or {})


def test_every_allowed_path_is_a_real_directory():
    missing = [a for a in (shelf().get("allow") or [])
               if not (REPO / "data" / a).is_dir()]
    assert missing == [], (
        "shelf allows path(s) that do not exist under data/: " + ", ".join(missing))


def test_the_shelf_is_not_accidentally_empty():
    """An empty or disabled allow list switches the gate off entirely, which
    would publish everything rather than nothing -- the opposite failure."""
    s = shelf()
    if s.get("enabled"):
        assert s.get("allow"), "shelf is enabled but allows nothing"


def test_manimanjari_is_on_the_shelf():
    """The specific regression: 306 verses landed and invisible."""
    allow = shelf().get("allow") or []
    assert any(a.endswith("Kavya/manimanjari") for a in allow), allow
