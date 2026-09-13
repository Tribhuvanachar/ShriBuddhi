# attic

Three files that were deleted from the public repository on purpose, and were
kept only by its git history.

`admin/README.md` said of the files it removed: "All of them remain in git
history if any is ever wanted back." That was true while the repository
existed. The old Buddhi is being replaced by a fresh repository carrying
content but not history, and then deleted — at which point the promise quietly
stops holding. These are the three files it would have broken for.

| File | Why it was removed | Still superseded by |
|---|---|---|
| `PrahladaKrutaNarasimhaStotra.html` | a standalone copy of one stotra, read by no code | the live text at `DvaitaVedanta/Itara/Stotra/prahlada_kruta_narasimha` |
| `apply_taxonomy_patch.py` | a one-off merge of the Kāvya genre tree into `taxonomy.json` | `tools/restructure_taxonomy.py` and `tools/migrate_slugs.py`, which are maintained |
| `nav-snippets.md` | two hand edits for a corpus package applied long ago | nothing — the edits are in the code |
| `lineage-3d.html` | a 3D guru-paramparā lineage view, dropped by the redesign — it appears nowhere in `tools/redesign/page_inventory.json`'s 84 rows | `pages/guru-parampara/lineage-2d.html`, which is the 2D view, not this one |

Nothing here is live. None of it is wired into a build, a test or a page, and
it is not meant to be. It is here so that deleting a repository does not also
delete the only copy of something a person may one day want to read.
