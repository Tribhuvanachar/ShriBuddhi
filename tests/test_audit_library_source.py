"""audit_library.py: syncing provenance must never lose provenance.

`--fix` derives each catalogue entry's `source` block from the grantha's own
data.json. Most data.json files declare only `source`; `source_url` and
`licence` were written straight into library.json by the importers and exist
nowhere else. Deriving fresh and overwriting therefore DELETED source_url
from 214 entries and licence from 197 -- among them the CC-BY 4.0
attributions for DCS and GRETIL, which are a promise the project made, not a
cache it can rebuild.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import audit_library  # noqa: E402

CC_BY = {
    "source": "Digital Corpus of Sanskrit (DCS), Oliver Hellwig, 2010-2024",
    "source_url": "https://github.com/OliverHellwig/sanskrit/tree/master/dcs",
    "licence": "CC-BY 4.0",
}


class DeriveSource(unittest.TestCase):
    def test_a_licence_the_file_does_not_mention_is_kept(self):
        payload = {"source": "Digital Corpus of Sanskrit (DCS), Oliver Hellwig, 2010-2024"}
        got = audit_library.derive_source(payload, CC_BY)
        self.assertEqual(got["licence"], "CC-BY 4.0")
        self.assertEqual(got["source_url"], CC_BY["source_url"])

    def test_what_the_file_does_declare_wins(self):
        payload = {"source": "ashtadhyayi.com (github.com/ashtadhyayi-com/data)"}
        got = audit_library.derive_source(payload, CC_BY)
        self.assertEqual(got["source"], payload["source"])
        self.assertEqual(got["licence"], "CC-BY 4.0")

    def test_nothing_changes_when_the_file_adds_nothing(self):
        self.assertEqual(audit_library.derive_source({}, CC_BY), CC_BY)

    def test_american_spelling_still_normalises(self):
        got = audit_library.derive_source({"license": "CC0"}, {"source": "x"})
        self.assertEqual(got["licence"], "CC0")
        self.assertNotIn("license", got)

    def test_a_new_entry_derives_from_the_file_alone(self):
        got = audit_library.derive_source({"source": "GRETIL", "licence": "CC-BY-SA"})
        self.assertEqual(got, {"source": "GRETIL", "licence": "CC-BY-SA"})

    def test_a_leaf_with_no_provenance_at_all_gets_no_block(self):
        self.assertIsNone(audit_library.derive_source({}))

    def test_an_unreadable_payload_does_not_erase_what_is_catalogued(self):
        self.assertEqual(audit_library.derive_source(None, CC_BY), CC_BY)

    def test_blank_values_in_the_file_do_not_blank_the_catalogue(self):
        got = audit_library.derive_source({"licence": "   ", "source_url": ""}, CC_BY)
        self.assertEqual(got, CC_BY)


if __name__ == "__main__":
    unittest.main()
