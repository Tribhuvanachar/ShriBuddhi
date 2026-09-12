from indic_transliteration import sanscript

# Testing several candidate ways of encoding "accented vocalic r" directly
# against the REAL library, since two guesses based on reasoning-from-the-
# outside have now both failed. This will show which (if any) it actually
# accepts, instead of guessing a third time.

candidates = {
    "1. precomposed ṛ (U+1E5B) + acute AFTER":      "\u1e5b\u0301",
    "2. acute BEFORE + precomposed ṛ (U+1E5B)":      "\u0301\u1e5b",
    "3. plain r + dot-below(U+0323) + acute AFTER":  "r\u0323\u0301",
    "4. plain r + acute + dot-below(U+0323) AFTER":  "r\u0301\u0323",
    "5. plain r + ring-below(U+0325) + acute AFTER": "r\u0325\u0301",
    "6. plain r + acute + ring-below(U+0325) AFTER (the ORIGINAL raw form)": "r\u0301\u0325",
    "7. plain r + dot-below, NO accent (control)":   "r\u0323",
    "8. plain r + ring-below, NO accent (control -- known to work already)": "r\u0325",
    "9. precomposed ṛ (U+1E5B) alone, NO accent (control)": "\u1e5b",
}

print("Testing each candidate wrapped as 'v' + candidate + 'ṣaṇam' (real word context):")
print("=" * 70)
for label, middle in candidates.items():
    test_word = "v" + middle + "ṣaṇam"
    try:
        result = sanscript.transliterate(test_word, sanscript.IAST, sanscript.DEVANAGARI)
    except Exception as e:
        result = f"ERROR: {e}"
    print(f"{label}")
    print(f"   input : {test_word!r}")
    print(f"   output: {result}")
    print()

print("=" * 70)
print("Also checking what scheme names are actually available, in case")
print("there's a Vedic-specific one better suited to this than plain IAST:")
print("=" * 70)
try:
    schemes = [s for s in dir(sanscript) if not s.startswith("_")]
    print(schemes)
except Exception as e:
    print("Could not list schemes:", e)
