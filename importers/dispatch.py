"""Single entry point for the workflow: python importers/dispatch.py <id>"""
import sys

# id -> (module, run-callable name) for the commentary/word-meaning importers
COMMENTARY = {
    "ramayana_saartha": ("ramayana_saartha", "run"),
    "mahabharata_ganguli": ("mahabharata_ganguli", "run"),
    "bhagavad_gita": ("bhagavadgita", "run"),
    "shankara_bhashya": ("shankara_bhashya", "run"),
}

def main(tid):
    if tid in ("bhagavata", "ramayana", "mahabharata"):
        mod = __import__(tid); mod.run()
    elif tid in COMMENTARY:
        modname, fn = COMMENTARY[tid]
        mod = __import__(modname); getattr(mod, fn)()
    elif tid.startswith("bulk:"):
        import gretil_bulk; gretil_bulk.run(tid.split(":", 1)[1])
    elif tid.startswith("chanakya_"):
        import chanakya
        chanakya.run(tid)
    elif tid == "kamandaki":
        import kamandaki
        kamandaki.run(tid)
    elif tid.startswith("wikisource_"):
        import wikisource_ayurveda
        wikisource_ayurveda.run(tid)
    elif tid == "darshana_all":
        import darshana_gretil as D
        for key in D.DARSHANA_GRETIL:
            try: D.run(key)
            except Exception as exc: print(f"  FAILED {key}: {exc}", file=sys.stderr)
    else:
        import gretil, itx, darshana_gretil
        if tid in gretil.GRETIL: gretil.run(tid)
        elif tid in darshana_gretil.DARSHANA_GRETIL: darshana_gretil.run(tid)
        elif tid in itx.ITX:     itx.run(tid)
        else:
            import gretil_bulk
            if tid in {t["id"] for t in gretil_bulk.load_registry()["texts"]}:
                gretil_bulk.run(tid)
            else:
                raise SystemExit(f"unknown text id: {tid}")

if __name__ == "__main__":
    if len(sys.argv) != 2: raise SystemExit("usage: dispatch.py <id>")
    main(sys.argv[1])
