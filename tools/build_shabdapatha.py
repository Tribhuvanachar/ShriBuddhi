#!/usr/bin/env python3
"""Build dge/data/vedanga/vyakarana/shabdapatha/data.json -- a Sanskrit noun
declension browser (Issue 15/19's "Shabda derivations") -- from
ashtadhyayi-com/data's shabda/data2.txt.

Only word, liGga (gender), the three short glosses (Sanskrit/Hindi/English)
and the 24-cell declension table are kept. shabda/shabda_meanings.txt (the
much larger multi-dictionary gloss blob keyed by the same urlid) is
deliberately NOT merged here: it overlaps in purpose with this repo's own
Kosha module (dge/js/kosha.js, dge/data/kosha/*, which already ships
Shabdakalpadruma etc.) rather than this declension feature, and folding a
second, differently-shaped dictionary source into Kosha wants its own pass
against Kosha's existing schema, not a rushed merge here.

One combined data.json (not per-word chunks): each entry is small once
trimmed to the fields above, so the whole file lands far below the size
where per-item chunking (as used for dhatuforms) would matter -- this
mirrors how dhatupatha/data.json itself ships as one file.

Usage:
    python3 tools/build_shabdapatha.py /path/to/ashtadhyayi-com/data
"""
import json
import sys
from pathlib import Path

LINGA = {"P": "पुंल्लिङ्गम्", "S": "स्त्रीलिङ्गम्", "N": "नपुंसकलिङ्गम्", "A": "अव्ययम्"}

SOURCE_NOTE = ("ashtadhyayi-com/data (github.com/ashtadhyayi-com/data, commit 24109f7, "
               "shabda/data2.txt); its README: \"free to use ... provided that "
               "appropriate credits are mentioned\". shabda_meanings.txt (multi-dictionary "
               "gloss blob) not merged -- overlaps this repo's own Kosha module, deferred "
               "to its own pass.")


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: build_shabdapatha.py /path/to/ashtadhyayi-com/data")
    src_file = Path(sys.argv[1]) / "shabda" / "data2.txt"
    src = json.loads(src_file.read_text(encoding="utf-8"))

    items = []
    for row in src["data"]:
        word, forms = row.get("word"), row.get("forms")
        if not word or not forms:
            continue
        item = {
            "id": row.get("urlid"),
            "word": word,
            "linga": row.get("linga"),
            "linga_iast": LINGA.get(row.get("linga"), row.get("linga")),
            "forms": forms,
        }
        if row.get("artha"): item["artha"] = row["artha"]
        if row.get("artha_hin"): item["artha_hin"] = row["artha_hin"]
        if row.get("artha_eng"): item["artha_eng"] = row["artha_eng"]
        items.append(item)

    out = {
        "schema": "vyakarana_shabdapatha",
        "source": SOURCE_NOTE,
        "count": len(items),
        "items": items,
    }
    out_path = (Path(__file__).resolve().parent.parent / "dge" / "data" / "vedanga"
                / "vyakarana" / "shabdapatha" / "data.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(items)} words -> {out_path} ({out_path.stat().st_size/1e6:.2f} MB)")


if __name__ == "__main__":
    main()
