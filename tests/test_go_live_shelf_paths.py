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


def test_every_path_on_the_public_root_shelf_is_a_real_directory():
    """The same check for config/library-overrides.json, the copy Jagat reads.
    The test above only looked at the admin copy, so the root copy kept
    `mani_manjari` (no such folder) after admin/ had been corrected: public
    readers would have seen nothing for Mani Manjari."""
    root = REPO / "config/library-overrides.json"
    allow = (json.loads(root.read_text(encoding="utf-8")).get("shelf") or {}).get("allow") or []
    missing = [a for a in allow if not (REPO / "data" / a).is_dir()]
    assert missing == [], (
        "public shelf allows path(s) that do not exist under data/: " + ", ".join(missing))


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


def test_rukminisha_vijaya_is_on_the_shelf():
    """1,171 verses across 19 sargas. Same exposure as maṇimañjarī: the data can
    be complete, library.json can list every sarga as populated, and the reader
    still answers "not part of the published library yet" if this one line is
    missing."""
    allow = shelf().get("allow") or []
    assert any(a.endswith("Kavya/rukminisha_vijaya") for a in allow), allow


def test_every_registered_kavya_leaf_is_populated():
    """A leaf registered populated=false renders as "Not Available Yet", which
    looks exactly like a deliberate hold, so nothing downstream flags it.
    register_layers.py's item_count() counted 0 for the whole Kavya shelf shape
    -- {metadata, shlokas: {...}} -- because it had drifted from the canonical
    one in audit_library.py despite a comment in each promising otherwise."""
    lib = json.loads((REPO / "data/library.json").read_text(encoding="utf-8"))
    bad = [g["path"] for g in lib["granthas"]
           if "/Kavya/" in g["path"] and not g.get("populated")
           and (REPO / g["path"]).is_file()]
    assert bad == [], bad


def test_venkatesa_mahatmya_is_on_the_shelf():
    """1,523 verses across 11 adhyāyas, with two commentaries."""
    allow = shelf().get("allow") or []
    assert any(a.endswith("uttara_parva/venkatesha_mahatmya") for a in allow), allow


def test_vaidika_svara_prakarana_is_on_the_shelf():
    """99 sūtras in four sections plus the prose between them. A Kannada work,
    the first on this shelf."""
    allow = shelf().get("allow") or []
    assert any(a.endswith("pratishakhya/vaidika_svara_prakarana") for a in allow), allow


def test_pasandakhandana_is_on_the_shelf():
    """129 verses with Surottama Tīrtha's vyākhyā, beside Vādirāja's own
    Yukti Mallikā."""
    allow = shelf().get("allow") or []
    assert any(a.endswith("Itara/pasandakhandana") for a in allow), allow


def test_ushaharana_is_on_the_shelf():
    """726 verses in nine sargas with the Rasikarañjanī."""
    allow = shelf().get("allow") or []
    assert any(a.endswith("Kavya/ushaharana") for a in allow), allow


def test_brhatisahasra_is_on_the_shelf():
    """986 of the work's 1000 verses, with the Tattvasāra."""
    allow = shelf().get("allow") or []
    assert any(a.endswith("Itara/brhatisahasra") for a in allow), allow


def test_upanishad_sarvasva_is_on_the_shelf():
    """25 Upaniṣads, 1,308 mantras with the Kannada tātparya. One allow entry
    covers all 25 folders, since dgeMatchShelf matches by prefix."""
    allow = shelf().get("allow") or []
    assert any(a.endswith("vedas/upanishad_sarvasva_kannada") for a in allow), allow


def test_the_public_and_admin_shelves_list_the_same_folders():
    """The admin copy is what an admin edits and tests against; the root copy is what Jagat
    publishes. They had drifted (the root copy kept four entries while the admin copy had fifteen,
    and `mani_manjari` survived in one after it was corrected in the other), so what an admin saw
    was not what a reader got. One list, two files: they must agree."""
    root = json.loads((REPO / "config/library-overrides.json").read_text(encoding="utf-8"))
    admin = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    assert (root.get("shelf") or root)["allow"] == (admin.get("shelf") or admin)["allow"]


def test_source_site_trees_are_not_on_the_shelf():
    """The lead, 1 Oct 2026: DvaitaVedantaIn, Anandamakaranda, Advaita Sharada and srivaishnavan's
    Meghamala stay hidden from Jagat. (The first three of those publish text only, under opaque ids;
    see tools/opaque_ids.py.) Kavya is the opposite: public in both."""
    allow = shelf().get("allow") or []
    for hidden in ("darshana/vedanta/dvaita/DvaitaVedantaIn", "darshana/vedanta/dvaita/Anandamakaranda",
                   "darshana/vedanta/advaita", "darshana/vedanta/vishishtadvaita/RamanujaMeghamala"):
        assert not any(a == hidden or a.startswith(hidden + "/") for a in allow), hidden
    assert "kavya_alankara" in allow
