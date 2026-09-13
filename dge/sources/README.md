# DGE source archive

Immutable acquisition archive per `dge/DGE_Madhva_Acquisition_Architecture.md` §24:
`sources/<institution>/<domain>/<year-or-range>/` holds the original artifact
plus a `source-manifest.json` recording where it came from, its hash, and what
is and isn't covered. Nothing here is normalized into DGE's site schema yet —
that's a separate, later step per source. Never overwrite a manifest's
`artifact_sha256`/`app_sha256` in place; a new acquisition gets a new
year-range folder (or a `-v2` suffix) so the history stays intact.

## Panchāṅga sources acquired so far (11 Sep 2026)

| institution | method | coverage | refresh strategy |
|---|---|---|---|
| Uttaradi Matha | packaged Flutter asset (`um_app_seed.db`) | 2024-02-29 → 2027-04-05, 4478 rows | **The live backend is now identified and confirmed AUTHORIZATION_REQUIRED, not just unrecoverable.** Firebase Realtime Database at `umapp-277119-default-rtdb.firebaseio.com` (project id, API key, storage bucket all found compiled into `resources.arsc` — survives even without `libapp.so`, since the Firebase Gradle plugin bakes `google-services.json` into Android string resources natively). Tested and confirmed properly secured: anonymous read denied on root and on `panchanga_data`/`paramparas`/`main_deities` specifically; the project also has anonymous sign-in disabled (`ADMIN_ONLY_OPERATION`), so there's no legitimate front door here at all, not even the one a real installer of the app would use. Not pursued further — see PENDING.md 11 Sep 2026 2:52pm entry. Practical refresh path stays: re-pull `um_app_seed.db` from each new Play Store version (Priority 4 in the architecture doc's acquisition order). |
| SRS Matha (Mantralaya) | packaged Flutter asset (JSON bundle) | 2026-03-01 → 2027-04-06, 402 rows | Same situation as Uttaradi — packaged JSON is the practical refresh path (new app version → new JSON) until an API is confirmed. Official site (`srsmatha.org/panchanga.php`) also publishes this; worth checking whether the site is friendlier to a scheduled re-check than waiting on app updates. |
| Vishwesha Panchanga (= Pejāvara's official Panchāṅga, see architecture doc §14/§18/§20) | packaged B4A asset (`vss4.vss`) | 2022-2026, **festival/special-day annotations only** | **Incomplete.** The full five-anga daily Panchāṅga is stored as opaque numeric codes in a separate file (`thithi.vss`, and only for 2020) whose decode logic lives in the app's compiled B4A bytecode — not yet reverse-engineered. The per-month files that look like data (`1-2025.vss` … `12-2026.vss`) are actually JPEG calendar-page scans, not text. Refresh strategy TBD until the decode work or a runtime capture happens. |

## Known gap: Udupi Panchanga

The architecture doc's Phase 1 order names Udupi Panchanga first. **Its APK
was not in the 11 Sep 2026 Drive delivery** (14 APKs arrived; Udupi wasn't
among them — confirmed by package-name inspection of all 14, including
ruling out "Hindu Calendar_9.2.1.apk," which is an unrelated third-party app,
`com.alokmandavgane.hinducalendar`, not a Udupi rebrand). Needs a supply
request back to whoever is gathering these.

## Known gap: no native code in this delivery's Flutter APKs

Uttaradi, Tithi Nirṇaya, and Vyāsarāja Matha Sosale all show `assets/flutter_assets/`
but **none of the three APKs in this delivery contain a `lib/` folder at
all** — no `libapp.so`, no `libflutter.so`, for any ABI. A Flutter app
cannot actually run without these; this is very likely a "base APK only"
export that's missing its ABI splits (see the architecture doc §6 — do not
conclude "no Flutter code" from one base APK). Practical effect: none of
these three can be installed and driven in an emulator as they are, and
none can have their real Dart logic (including hardcoded API endpoints)
inspected via `strings` on `libapp.so`, because that file isn't here. Getting
the full split bundle (or an APK exported as one merged/universal APK that
actually includes native libs) is a prerequisite for the runtime/network
capture phase (architecture doc §7-9) on these three sources.

## Deliberately not archived

- `ph.vss` (Vishwesha app) is a directory of pontiffs' names + personal phone
  numbers. Not archived here — this is personal contact data and needs an
  explicit rights/consent call before any use, per architecture doc §49/§67.
- `bank_account_table` inside the Uttaradi seed db. Sensitive institutional
  financial data; never to be extracted or published.
