#!/usr/bin/env python3
"""
Regression test for the from-scratch chandas engine (scan.py + build_db.py
+ identify.py). Every verse below is a real classical verse recalled
independently (not constructed to fit a pattern), except where noted --
each is checked against its well-known, correctly-identified metre.

Run: python3 tools/chandas_native/verify.py
"""
import sys

from identify import identify, load_db

CASES = [
    (
        "धर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः "
        "मामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय",
        "अनुष्टुभ्",
        "Bhagavad Gita 1.1 -- opening shloka",
    ),
    (
        "विद्या नाम नरस्य रूपमधिकं प्रच्छन्नगुप्तं धनम् "
        "विद्या भोगकरी यशःसुखकरी विद्या गुरूणां गुरुः",
        "शार्दूलविक्रीडित",
        "Bhartrhari, Nitishataka -- verse in praise of learning",
    ),
    (
        "यां चिन्तयामि सततं मयि सा विरक्ता "
        "साप्यन्यमिच्छति जनं स जनोऽन्यसक्तः",
        "वसन्ततिलका",
        "Bhartrhari, Nitishataka -- the chain of unrequited desire",
    ),
]


def main():
    db = load_db()
    failures = 0
    for verse, expected, source in CASES:
        result = identify(verse, db)
        name = result["name"]
        ok = name == expected or (isinstance(name, list) and expected in name)
        status = "OK" if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"[{status}] {source}")
        print(f"       expected={expected!r} got={result}")
    if failures:
        print(f"\n{failures} verification case(s) failed")
        sys.exit(1)
    print(f"\nall {len(CASES)} verification cases passed")


if __name__ == "__main__":
    main()
