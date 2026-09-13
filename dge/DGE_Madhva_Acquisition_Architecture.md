# DGE — Madhva Institutional Knowledge, Panchāṅga & Matrimony Acquisition
## Cloud Code / Autonomous APK & Web Source Research Specification

**Document purpose:** Give Cloud Code a complete, execution-oriented specification for continuing the DGE research/acquisition task to completion.

**Prepared from:** the APKs and extracted application artifacts supplied in this conversation, plus targeted web verification of current official sources.

**Status:** Architecture + research findings + implementation plan.
**Important:** This document deliberately distinguishes **observed facts**, **strong inferences**, and **things that still require runtime verification**.

---

## Correction log

**11 Sep 2026 — project lead's ruling on two acquisition targets, before any implementation started.** This is the first time this specification has been committed to the repo, and the project lead reviewed it and corrected two points in the source inventory before Phase 1 work begins. Both corrections are applied throughout the document below (§18, §19, §20, §23, §38–39, §58, §62, §73), not just noted here:

1. **Śrīpādarāja Maṭha has no app or website currently available to us.** The §19 findings below (an official site URL, a historical Android package name) came from general web verification, not from confirming a live, accessible source. Until one is actually confirmed reachable, Śrīpādarāja is **not part of the current acquisition inventory** — it is a **future acquisition target only**. It stays in the institutional/source registry as a named placeholder with status `NOT_YET_ACQUIRED`, so the registry doesn't forget the institution exists, but no Phase 1/2 work is scheduled against it yet.
2. **Pejāvara Maṭha and Viśveśa Pañcāṅga are the same source/institutional stream, not two acquisition targets.** Viśveśa Pañcāṅga is Sri Pejāvara Adhokshaja Maṭha's own official Panchāṅga (named for the maṭha's pontiff, Sri Vishwesha Teertha) — institutional name and product name differ, but the underlying data source does not. The existing Viśveśa Pañcāṅga adapter/source covers Pejāvara's Panchāṅga; there is no separate "Pejāvara Panchāṅga" acquisition or adapter. The earlier recommendation to separately acquire/analyze a Pejāvara app/site **for Panchāṅga purposes** is withdrawn. Pejāvara Maṭha's broader institutional knowledge (paramparā, deities, branches, photos, history, events, publications) is unaffected by this and still gets acquired from the maṭha's own official website, per §18.

This is also a standing architectural rule going forward, not a one-off fix: **one institutional/source adapter per actual data source**, never two adapters merely because an institution's name and a product's name differ. Before registering a new source, check whether it is actually the same underlying data as an existing one under a different label.

---

# 1. Executive objective

DGE should become a source-aware digital knowledge platform for the Madhva/Dvaita tradition, with three major acquisition domains:

1. **Mutt-specific Panchāṅgas**
   - Preserve each institution's own Panchāṅga identity and methodology.
   - Acquire every available year.
   - Prefer structured official data/API/database when legitimately available.
   - Otherwise ingest official annual PDFs or other published artifacts.
   - Never silently substitute a generic astronomical calculation for an institution's own Panchāṅga.

2. **Mutt institutional knowledge**
   - Maṭha history
   - Paramparā / pontiff lineage
   - Mūla Pratimās
   - Sthāna Pratimās / other worshipped deities
   - Individual deity photographs
   - Descriptions and historical narratives
   - Branches / kṣetras / temples
   - Publications
   - Events
   - Seva information
   - Official contacts and websites
   - Source provenance

3. **Madhva matrimonial service**
   - Profiles for brides/grooms
   - Photos
   - Preferences and matching criteria
   - Interest / invitation workflow
   - Mutual acceptance
   - Controlled contact disclosure
   - WhatsApp / phone / email contact preferences
   - Identity/contact verification
   - Optional institutional/Ācārya attestation
   - Audit trail and consent
   - Strong privacy and deletion controls

The system should be implemented as a **source-adapter architecture**, not as one giant scraper.

---

# 2. Core architectural principle

DGE must distinguish:

> **What the source says**

from

> **What DGE computes**

and from

> **What DGE infers or normalizes**.

For example:

```text
SOURCE
  ↓
Official Mutt App / Website / API / PDF / Database
  ↓
Acquisition
  ↓
Immutable Source Artifact
  ↓
Parser / Extractor
  ↓
Normalized DGE Entity
  ↓
Validation
  ↓
Publication
```

Every normalized record must retain provenance back to the source artifact.

---

# 3. Critical design decision: Panchāṅga is source-specific

Do NOT implement:

```text
DGE generic astronomical engine
        ↓
all Mutt Panchāṅgas
```

as the primary model.

Instead:

```text
Uttarādi source
Vyāsarāja source
Sode/Tithi Nirṇaya source
SRS source
Udupi source
Vishwesha source (also Pejāvara's official Panchāṅga — one source, see §18/§20)
Śrīpādarāja source (future — see §19)
...
        ↓
DGE normalized Panchāṅga model
```

Different institutions can legitimately have different:

- siddhānta basis
- location
- sunrise/sunset conventions
- tithi boundaries
- Ekādaśī determination
- festival observance
- māsa interpretation
- special institutional observances

DGE must preserve those differences.

---

# 4. Acquisition priority

For every source, use this preference order:

### Priority 1 — Official structured API

Example:

```text
GET /api/panchanga/2026
POST /panchanga/query
```

Acquire the structured response, if the endpoint is publicly/legitimately accessible.

### Priority 2 — Official database / downloadable structured data

SQLite, JSON, CSV, XLSX, etc.

### Priority 3 — Official annual PDF

Download and archive the original.

### Priority 4 — Official application assets

If the APK itself contains annual Panchāṅga data, extract the assets.

### Priority 5 — Official website pages

Use web acquisition where structured or downloadable content is unavailable.

### Priority 6 — UI scraping

Only when the underlying data cannot otherwise be obtained.

### Priority 7 — Manual transcription

Last resort, with human validation.

---

# 5. APK research framework

Cloud Code should create an autonomous APK analysis pipeline.

## 5.1 Static APK analysis

For each APK:

```text
APK
 ├── package name
 ├── version
 ├── signing metadata
 ├── min/target SDK
 ├── activities
 ├── services
 ├── receivers
 ├── providers
 ├── permissions
 ├── DEX files
 ├── native libraries
 ├── assets
 ├── resources
 ├── embedded DBs
 ├── JSON/XML
 ├── PDFs
 ├── images
 ├── audio/video
 └── URLs/domains
```

Identify framework:

- Flutter
- React Native
- native Android
- Basic4Android
- WebView-heavy
- hybrid

---

# 6. Flutter-specific workflow

A supplied APK can be incomplete with respect to the complete Flutter delivery payload.

Therefore Cloud Code must first determine:

```text
Is the APK self-contained?
```

Check:

```text
lib/arm64-v8a/libapp.so
lib/arm64-v8a/libflutter.so
lib/armeabi-v7a/...
assets/flutter_assets/
AssetManifest.*
NativeAssetsManifest.json
split APK relationships
```

If `libapp.so` is absent:

1. determine whether the supplied artifact is a base/split APK;
2. inspect Play/App Bundle delivery metadata if legitimately available;
3. reconstruct the installed package from all authorized splits if available;
4. only then conclude that Dart AOT code is unavailable.

Do not infer "no Flutter code" merely from one base APK.

Flutter also supports deferred components, so separately delivered AOT components must be considered.

---

# 7. Runtime Android analysis

Where permitted, Cloud Code should provision an Android emulator.

Recommended components:

```text
Android SDK
ADB
AVD
system image
Google APIs / Play Store where required
```

Then:

```text
install APK
launch app
wait for startup
capture UI hierarchy
capture screenshots
enumerate activities
navigate menus
record actions
observe storage
observe network
```

Playwright may be used for browser/WebView/UI automation, but it should not be treated as the only Android instrumentation mechanism.

For native Android networking, prefer:

```text
ADB
emulator
HTTP(S) proxy
runtime instrumentation
application-level logging where appropriate
```

---

# 8. Network discovery workflow

For each app:

```text
STATIC URL DISCOVERY
        ↓
KNOWN DOMAINS
        ↓
RUNTIME CAPTURE
        ↓
REQUEST/RESPONSE INVENTORY
        ↓
CLASSIFY ENDPOINTS
        ↓
REPLAY NON-AUTHENTICATED PUBLIC REQUESTS
        ↓
BUILD SOURCE ADAPTER
```

Record:

```text
domain
URL
method
query parameters
request headers
request body shape
response status
response content type
response schema
authentication requirement
location/year parameters
pagination
cache behavior
rate limits
```

Do NOT attempt to defeat authentication, certificate pinning, device attestation, paywalls, or access controls. If data is protected, mark it as requiring authorized access/export.

---

# 9. Network capture levels

### Level A — browser/WebView

Use Playwright network instrumentation.

### Level B — standard Android HTTP

Use an emulator proxy / network capture.

### Level C — Retrofit / OkHttp / Dio

Identify the library and observe requests at the networking boundary.

### Level D — local cache

Run the app, then inspect the application cache/database after the content has been downloaded.

### Level E — native/encrypted transport

Only if necessary and only within authorized access. Document the limitation rather than bypassing security controls.

---

# 10. Current APK research findings

## 10.1 Śrī Uttarādi Maṭha 1.9.0

### Strong finding

The APK contains:

```text
assets/flutter_assets/assets/um_app_seed.db
```

The database has a dedicated:

```text
panchanga_table
```

and:

```text
panchanga_pdf_table
panchangas_table
sync_timestamps_table
```

### Panchāṅga schema observed

The local table contains:

```text
id
date
month
sun_rise
sun_set
ayana
rutu
masa
masa_niyamaka
paksha
tithi
vasara
nakshatra
yoga
karna
shuba_ashuba
shraddha_tithi
samvatsara
today_spl
aradana
ekadasi_type
tarpana
festivals
details
parampara_slug
language
show_in_aradane
show_in_ekadashi
show_in_festival
show_in_tarpana
show_in_shuba_ashuba
```

### Observed volume

The supplied database contains approximately:

```text
4,478 panchanga rows
```

with dates covering approximately:

```text
2024 → 2027
```

and languages including:

```text
English
Kannada
Sanskrit
Tamil
Telugu
```

The annual PDF registry contains years:

```text
2017-2018
2018-2019
2019-2020
2020-2021
2021-2022
2022-2023
2023-2024
2024-2025
2025-2026
2026-2027
```

The current 2026–27 entries include official CDN URLs under:

```text
https://cdn.umath.in/panchanga-2026-2027/
```

The app therefore provides an unusually good model for DGE:

```text
official annual Panchāṅga
        ↓
structured local DB
        ↓
app rendering
        ↓
sync/update mechanism
```

### Important additional finding

The same database contains:

```text
main_deities_table
parampara_table
gallery_table
generic_media_table
```

This means the Uttarādi APK is not merely a Panchāṅga source.

It is already a model for DGE's institutional knowledge acquisition.

In particular, `main_deities_table` contains:

```text
name
sloka
image_path
content
```

and `parampara_table` contains fields such as:

```text
title
slug
audio_url
content
thumbnail_url
sloka_sanskrit
sloka_english
poorvasharama_name
ashrama_name
preceptor
years_in_pitha
brindavana_at
aradhane
works
contact_details
contact_map
```

### DGE action

Uttarādi should be the first production-grade institutional adapter.

---

# 11. SRS Matha Panchanga 2.0.0

This is another exceptionally important discovery.

The current supplied APK contains Flutter assets including:

```text
assets/flutter_assets/assets/data/panchanga_bundle/panchanga.en.json

assets/flutter_assets/srsmatha.org/srsmatha_panchanga/storage/
    sacred_calendars/aradhana.json
    sacred_calendars/ekadashi.json
    sacred_calendars/festivals.json
    sacred_calendars/tarpana.json
```

## Panchāṅga is explicitly pre-curated in the APK

The supplied JSON contains:

```text
402 daily Panchāṅga records
```

covering approximately:

```text
2026-03-01 → 2027-04-06
```

The records contain:

```text
id
date
gregorian_date
location_name
day
panchanga_day
samvatsara
ayana
ritu
masa
paksha
tithi
nakshatra
yoga
karana
sunrise
sunset
rahukaala
gulikaala
yamaganda
festival
shraddha
masaniyamaka
```

Additional curated datasets include:

### Arādhana

Approximately 41 records covering 2026–27.

Fields include:

```text
date
title
place
audioUrl
shloka
description
imageUrl
sourceUrl
sourceReference
biography
```

### Ekādaśī

Approximately 26 records.

### Festivals

Approximately 45 records, with:

```text
date
title
subtitle
description
notes
sourceUrl
```

### Tarpana

Approximately 103 records, with:

```text
date
title
category
printed_index
description
notes
```

## DGE action

This should be ingested as:

```text
Panchāṅga
Festival
Ekādaśī
Ārādhana
Tarpana
```

as separate but linked source collections.

The official SRS website also currently exposes a Panchāṅga page and annual PDF downloads, and the official Play listing describes the app as the SRS Matha Panchanga. These should be used for source validation.

---

# 12. Older SRS Matha 2.0 APK

The older supplied APK is materially different.

It exposes a hard-coded endpoint:

```text
https://srsmatha.org/srsapp/dbupd.php
```

and the SRS site endpoint:

```text
https://www.srsmatha.org/srsapp/?p=srsmatha
```

This strongly suggests a database-update architecture.

DGE should investigate both:

```text
old app update endpoint
current 2.0.0 packaged JSON
official web Panchāṅga
official annual PDFs
```

The current 2.0.0 package is the better structured source for 2026–27, but the older update endpoint may help reconstruct historical data acquisition.

---

# 13. Udupi Panchanga UP26.v.26

This APK is **not Flutter**.

It is a large native/Basic4Android-style application with:

```text
assets/*.bal
assets/*.vss
assets/*.txt
assets/*.xlsx
assets/*.mp3
```

The `.bal` files are B4A-style layout artifacts.

The most important discovery is that the APK contains substantial Panchāṅga data locally.

Examples:

```text
assets/2023.txt
assets/2023-26.9.xlsx
assets/vss6.vss
assets/vss6t.vss
assets/vss4.vss
assets/vss4t.vss
assets/vssth.vss
assets/vsstht.vss
assets/thithi.vss
...
```

`2023.txt` contains daily Panchāṅga records with fields such as:

```text
Samvatsara
Ayana
Dhanur/Māsa
Rutu
Pousha/Māsa
Paksha
Tithi + ending time
Vāsara
Nakṣatra + ending time
Yoga
Karaṇa
Māsa Niyamaka / observance
```

The file contains hundreds of daily lines.

The XLSX file contains multiple sheets, including:

```text
app panchanga
final 2022
Sheet8
Sheet11
Sheet12
Sheet13
...
```

and structured daily Panchāṅga fields.

There are also many `.vss` files containing plain-text daily Panchāṅga data and calendar/event information.

Some `.vss` files with names like:

```text
1-2025.vss
1-2026.vss
2-2025.vss
2-2026.vss
...
12-2025.vss
12-2026.vss
```

are actually JPEG-formatted image assets despite the `.vss` extension.

This means the application has both:

```text
structured/textual Panchāṅga
+
calendar/image presentation assets
```

inside the APK.

## Conclusion

For the supplied build, Udupi Panchanga is clearly **pre-curated / packaged-data driven**, not a purely runtime astronomical calculation.

It should be treated as:

```text
annual/monthly curated data
        ↓
local app assets
        ↓
rendering
```

The app may still have update/download behavior, so Cloud Code should inspect the download service and runtime network calls before deciding that future years can only be obtained by replacing the APK.

---

# 14. Vishwesha Panchanga V.26

This application is strikingly similar to the Udupi Panchanga application.

It shares a large portion of the same assets/layout architecture.

The two APKs have:

- hundreds of identical asset hashes
- the same B4A-style `.bal` layouts
- common `.vss` data conventions
- common calendar/Panchāṅga structure
- common audio/assets

but also have source-specific differences.

Vishwesha adds source-specific assets such as:

```text
assets/vishwesha.jpg
assets/vishwesha.mp3
assets/ph.vss
assets/phold.vss
assets/add.vss
assets/add1.vss
assets/masikacal.bal
assets/searchaddress.bal
assets/searchph.bal
```

while Udupi has source-specific assets such as:

```text
assets/2023.txt
assets/vss7.vss
assets/vss8.vss
assets/vss9.vss
assets/vss10.vss
assets/vss11.vss
assets/vss12.vss
...
```

## Important conclusion

These appear to be **closely related applications built from a common code/data framework**, but with different institutional/source content.

Therefore Cloud Code should not build two completely independent crawlers.

Create:

```text
B4A Panchanga Adapter
```

with:

```text
source configuration
asset naming rules
institution-specific data mapping
```

and then instantiate:

```text
Udupi adapter
Vishwesha adapter
```

as separate source configurations.

**Vishwesha Panchanga is Sri Pejāvara Adhokshaja Maṭha's own official Panchāṅga** (named for the maṭha's pontiff, Sri Vishwesha Teertha). It is not a separate institution from Pejāvara for acquisition purposes — see the correction log above and §18/§20. Do not create a separate "Pejāvara adapter"; the Vishwesha adapter instance *is* Pejāvara's Panchāṅga source.

---

# 15. Tithi Nirṇaya Panchanga 2.0.3

The supplied APK is Flutter.

The Android/native side contains:

```text
com.krishna.panchanga_app.MainActivity
com.krishna.panchanga_app.SunriseSunsetWidgetReceiver
```

and the deep-link style string:

```text
tnp://panchanga
```

However, the supplied APK does not expose the normal Flutter AOT native payload needed to recover the full Dart implementation.

Therefore:

### Do NOT conclude

"it is runtime generated"

or

"it is pre-curated"

from this APK alone.

The correct status is:

```text
UNRESOLVED — requires complete Flutter delivery artifact
or runtime/network investigation.
```

The official app description states that it follows the Sode Śrī Vādirāja Maṭha Panchāṅga and says the Panchāṅga is based on Āryabhaṭa Siddhānta.

DGE must preserve that institutional identity.

Cloud Code should:

1. identify whether this APK is a base/split/incomplete Flutter artifact;
2. reconstruct all authorized splits if possible;
3. locate `libapp.so`;
4. statically inspect strings/assets;
5. run the app;
6. capture Panchāṅga interactions;
7. capture network activity;
8. inspect any local cache after opening multiple dates;
9. determine whether the data are:
   - calculated,
   - packaged,
   - downloaded,
   - or hybrid.

---

# 16. Sōde Maṭha 3.3

The supplied app is a native Android application.

It contains Retrofit/OkHttp-related infrastructure and explicit Sode URLs such as:

```text
https://sodematha.in/
https://sodematha.in/app/
https://sodematha.in/branch
https://sodematha.in/dailyworship
https://sodematha.in/history
https://sodematha.in/parampara
https://sodematha.in/profile?id=
https://sodematha.in/sode
https://sodematha.in/eventdetails?id=
...
```

This is particularly important for the DGE institutional-knowledge objective.

The current official Sode website now exposes dedicated content for:

- Paramparā
- Deities
- Daily worship
- Branches
- History
- Publications
- Events

The official Daily Worship page explicitly provides descriptions for deities including:

```text
Sri Bhuvaraha
Sri Hayagriva
Sri Lakshmi Narasimha
Sri Vitthala
Lord Srinivasa with Sri and Bhu
Srimushnavaraha
Saligrama Samputa
Sri Vishvambhara Saligrama
Hayagriva Saligrama
...
```

This demonstrates exactly the type of structured religious/institutional content DGE should model.

## Sode institutional tree

Cloud Code should extract:

```text
Sode Matha
├── Parampara
├── Daily Worshipped Deities
│   ├── deity
│   ├── image
│   ├── description
│   ├── historical origin
│   └── worship status
├── Branches
│   ├── branch
│   ├── location
│   ├── deities
│   ├── history
│   └── images
├── History
├── Events
└── Publications
```

The current official website should be treated as an important source alongside the legacy app.

---

# 17. Vyāsarāja Maṭha / Sosale 22.0.0

The supplied app is Flutter.

The APK contains:

```text
assets/flutter_assets/
```

but no Panchāṅga SQLite database is present.

The public application release history describes:

```text
Panchanga alerts
Offline Panchanga
real-time updates
latest content
```

Therefore the likely architecture is:

```text
server/admin content
      ↓
app cache
      ↓
offline Panchāṅga
```

but the exact endpoint was not established statically from the supplied base APK.

## Cloud Code requirement

Run:

```text
complete Flutter reconstruction
+
runtime navigation
+
network capture
```

and identify:

```text
Panchāṅga endpoint
year parameter
location parameter
response schema
cache/database format
PDF/image endpoints
admin/content endpoints
```

Do not rely on public release notes as proof of the exact API.

---

# 18. Pejāvara Maṭha

**Corrected 11 Sep 2026 — see the Correction log above.** Pejāvara is *not* a separate Panchāṅga acquisition target: its official Panchāṅga is Viśveśa Pañcāṅga (§14), already covered by the Vishwesha adapter/source. There is no separate "Pejāvara Panchāṅga" APK or site to acquire, and none should be sought. What follows below is scoped to Pejāvara Maṭha's *institutional* knowledge only (paramparā, deities, branches, history, etc.), which is a genuinely separate acquisition target from the Panchāṅga question and is unaffected by this correction.

Official website:

```text
https://pejavaramatha.in/
```

The official site identifies the institution as:

```text
Sri Pejavara Adhokshaja Matha
Udupi
Jagadguru Sri Madhwacharya Samsthana
```

and provides institutional material including history, centres, and deity information.

The site states that the idol worshipped in the Pejāvara Matha is Vithala with Śrīdevī and Bhūdevī, described as Aja Vithala.

## DGE target

Acquire, from the official website (Priority 5, §4) — **not** as a separate Panchāṅga acquisition:

```text
Pejāvara paramparā
Pejāvara deities
Mūla Pratimā
branch/centre information
photos
descriptions
events
publications
```

Pejāvara's Panchāṅga is Viśveśa Pañcāṅga — see §14/§20 for the shared source, and do not duplicate it here.

---

# 19. Śrīpādarāja Maṭha — future acquisition target, not yet in the active inventory

**Corrected 11 Sep 2026 — see the Correction log above.** No app or website for Śrīpādarāja Maṭha is currently available to us. The findings below come from general web verification during earlier research, not from confirming a live, reachable source, and must not be treated as an existing source in the current acquisition inventory. Śrīpādarāja is a **future acquisition target only**: it stays named in the institutional/source registry (§20) as a placeholder with status `NOT_YET_ACQUIRED`, and no Phase 1/2 work is scheduled against it (§58) until an actual accessible app or website is confirmed.

Unconfirmed findings from earlier research, kept here for when this target is revisited:

```text
possible official website: https://www.sripadarajamutt.org/
```

The institution is at:

```text
Narasimhatheertha, Mulbagal
Kolar District, Karnataka
```

A historical Android application package name was also identified publicly:

```text
package: com.ssprm.sspmuser
```

described in an old listing as the official mobile app of Sri Sripadaraja Math, Mulbagal — status of that listing (still published, still installable) is unconfirmed.

## When this target is revisited (not now)

1. confirm whether the website above is actually live and reachable;
2. confirm whether the app above (or a current successor) is still distributed;
3. only once one of those is confirmed, obtain an authorized APK or crawl the site;
4. analyze for Panchāṅga, Paramparā, deity/pratima content, photos, seva, publications, events, contact information;
5. preserve source provenance.

Until then: no acquisition action, no adapter, no registry entry beyond the `NOT_YET_ACQUIRED` placeholder.

---

# 20. Recommended institutional registry

Start with at least:

```text
Sri Uttaradi Matha
Sri Sode Vadiraja Matha
Sri Vyasaraja Matha, Sosale
Sri Raghavendra Swamy Matha / SRS Matha
Sri Pejavara Adhokshaja Matha        (Panchanga source: Vishwesha/Viśveśa — see below; institutional knowledge: own website, §18)
Sri Sripadaraja Matha                (registry placeholder only — status NOT_YET_ACQUIRED, no current app/website confirmed accessible, see §19)
Udupi Panchanga source
Vishwesha Panchanga source           (= Sri Pejavara Adhokshaja Matha's official Panchanga; not a separate institution for acquisition purposes)
Tithi Nirṇaya Panchanga
```

Then expand to the remaining Madhva institutions.

Do not assume "Udupi Panchanga" and "Vishwesha Panchanga" are separate Maṭhas merely because they are separate apps. Determine the actual institutional publisher/source identity — this is exactly the check that caught Pejāvara/Vishwesha as one source rather than two (§14/§18), and the same check must be applied before registering any future source, not only this one.

---

# 21. Canonical DGE Panchāṅga model

Recommended logical schema:

```text
panchanga_source
----------------
id
institution_id
source_name
tradition
methodology
source_type
official_url
app_package
app_version
year
location_name
latitude
longitude
timezone
language
source_artifact_id
source_hash
retrieved_at
parser_version
rights_status
verification_status
```

```text
panchanga_day
-------------
id
source_id
date
gregorian_date
location
day_name
samvatsara
ayana
ritu
masa
masa_niyamaka
adhika_masa
paksha
tithi
tithi_end
vasara
nakshatra
nakshatra_end
yoga
karana
sunrise
sunset
rahukaala
gulikaala
yamaganda
shubha_ashubha
shraddha_tithi
ekadashi_type
tarpana
festival
aradhana
special
details
source_record_id
```

---

# 22. Never discard the source-specific fields

Do not force every source into a lowest-common-denominator schema.

Keep:

```text source_specific_json
```

or an equivalent extensible field.

For example, Uttarādi has flags such as:

```text show_in_aradane
show_in_ekadashi
show_in_festival
show_in_tarpana
show_in_shuba_ashuba
```

These should not be lost during normalization.

---

# 23. Panchāṅga year acquisition model

DGE should maintain:

```text
panchanga_year_registry
```

with:

```text institution
year
source_status
artifact_status
structured_status
parsed_status
validated_status
published_status
```

Example:

```text
Uttaradi   | 2026-27 | acquired        | parsed  | validated | published
SRS        | 2026-27 | acquired        | parsed  | validated | published
Sode       | 2026-27 | API TBD         | pending | pending   | pending
Vyasaraja  | 2026-27 | API TBD         | pending | pending   | pending
Vishwesha  | 2026-27 | pending         | pending | pending   | pending   (this row also covers Pejāvara — see §18/§20)
Sripadaraja| —       | NOT_YET_ACQUIRED| —       | —         | —         (future placeholder only — see §19)
```

Note there is no separate "Pejavara" row: Pejāvara's Panchāṅga is the Vishwesha row above.

This allows the system to discover the next missing year automatically.

---

# 24. Immutable source archive

Every acquisition should store the original artifact:

```text
sources/
  institution/
    panchanga/
      2026-27/
        original.pdf
        original.json
        original.sqlite
        source-manifest.json
```

`source-manifest.json`:

```json
{
  "institution": "Example Matha",
  "year": "2026-27",
  "source_url": "...",
  "retrieved_at": "...",
  "sha256": "...",
  "content_type": "...",
  "method": "official_api|official_pdf|apk_asset|website",
  "parser": "...",
  "rights_status": "..."
}
```

---

# 25. Institutional knowledge graph

DGE should not flatten Maṭha knowledge into pages.

Use a graph-like model:

```text
MATHA
 |
 +-- PARAMPARA
 |     |
 |     +-- ACHARYA
 |           |
 |           +-- aradhana
 |           +-- brindavana
 |           +-- works
 |           +-- biography
 |
 +-- DEITY
 |     |
 |     +-- MULA_PRATIMA
 |     +-- STHANA_PRATIMA
 |     +-- SALIGRAMA
 |     +-- TEMPLE
 |     +-- IMAGE
 |
 +-- BRANCH
 |
 +-- KSHETRA
 |
 +-- PANCHANGA
 |
 +-- FESTIVAL
 |
 +-- PUBLICATION
 |
 +-- EVENT
```

---

# 26. Pratimā / deity canonical model

```text
deity
-----
id
institution_id
name
alternate_names
deity_type
status
description
historical_origin
worship_description
sthala_id
parampara_relation
source_primary
verification_status
```

```text
deity_image
-----------
id
deity_id
source_url
original_url
storage_url
caption
source_institution
source_artifact
sha256
perceptual_hash
rights_status
retrieved_at
```

```text
deity_relationship
------------------
parent_deity
child_deity
relationship_type
sequence
```

This supports the requested tree view.

---

# 27. Example Sode tree

```text
Sri Sode Vadiraja Matha
|
+-- Daily Worshipped Deities
|    |
|    +-- Sri Bhuvaraha
|    +-- Sri Hayagriva
|    +-- Sri Lakshmi Narasimha
|    +-- Sri Vitthala
|    +-- Sri Srinivasa
|    +-- Sri Srimushnavaraha
|    +-- Saligrama Samputa
|    +-- Sri Vishvambhara Saligrama
|    +-- Hayagriva Saligrama
|
+-- Branches
|    +-- Udupi
|    +-- Sode
|    +-- Nadyantadi
|    +-- Bilagi
|    +-- Gokarna
|    +-- ...
|
+-- Parampara
|
+-- History
|
+-- Events
|
+-- Publications
```

This is illustrative of the data model; Cloud Code must extract and source the actual list rather than hard-code it.

---

# 28. Image deduplication

The same deity may appear in:

- official website
- old app
- new app
- PDF
- social media
- another institutional source

Do not create duplicate image records blindly.

Calculate:

```text
SHA-256
perceptual hash
dimensions
mime type
```

Then retain multiple provenance relationships to the same underlying image when appropriate.

---

# 29. Content confidence

Every extracted entity should receive a confidence state:

```text
OFFICIAL_STRUCTURED
OFFICIAL_DATABASE
OFFICIAL_PDF
OFFICIAL_APP_ASSET
OFFICIAL_WEBSITE
OFFICIAL_SOCIAL
SECONDARY
UNVERIFIED
```

And:

```text
verified
needs_review
conflict
deprecated
retracted
```

---

# 30. Matrimony — source research finding

The supplied UM Matrimony React Native bundle clearly exposes a live application model.

Observed conceptual features include:

```text
matching profiles
shortlisted profiles
favourites
send invitation
accept invitation
reject invitation
cancel invitation
report profile
block/unblock
profile details
advanced details
mobile/email verification
OTP
photo upload
contact preferences
contact disclosure
Prime membership
WhatsApp/contact preferences
```

The application bundle contains the API domain:

```text
https://api.umapps.in
```

and site/application URLs under:

```text
https://srijspnvvs.umapps.in/
```

The exact endpoint paths should be recovered from a complete APK/runtime capture rather than guessed from UI strings.

---

# 31. Matrimony interaction model

The desired DGE model is:

```text
PROFILE A
   |
   | Express Interest
   v
PENDING INVITATION
   |
   | Accept
   v
MUTUAL CONNECTION
   |
   v
CONTACT DISCLOSURE
```

Reject:

```text
A → interest → B
B → reject
```

must terminate the invitation without exposing private contact information.

---

# 32. Contact privacy

Do not create a public directory containing every person's:

- mobile number
- WhatsApp number
- email
- photographs

unless the user has explicitly consented to that publication.

Recommended:

```text
contact_visibility
------------------
public
registered_users
mutual_connection
verified_connection
manual_approval
private
```

Default should be restrictive.

---

# 33. Matrimony data model

```text
matrimonial_profile
-------------------
id
user_id
profile_type
display_name
gender
date_of_birth
age
education
profession
location
languages
gotra
pravara
nakshatra
rashi
madhva_affiliation
matha_affiliation
family_details
bio
contact_preference
profile_status
created_at
updated_at
deleted_at
```

```text
profile_photo
-------------
id
profile_id
storage_key
thumbnail_key
sort_order
visibility
consent_status
source
hash
created_at
```

```text
match_preference
----------------
profile_id
age_min
age_max
education
profession
location
gotra_constraints
matha_constraints
nakshatra_constraints
family_preferences
other_preferences
```

---

# 34. Interest/invitation model

```text
profile_interest
----------------
id
from_profile
to_profile
status
message
created_at
responded_at
expires_at
```

Statuses:

```text
pending
accepted
rejected
withdrawn
blocked
expired
```

---

# 35. Institutional verification / Ācārya attestation

This should NOT simply be a green check mark.

Create:

```text
profile_attestation
-------------------
id
profile_id
issuer_id
issuer_type
attestation_type
statement
evidence
issued_at
valid_until
status
revoked_at
source
signature_reference
notes
```

Issuer types:

```text
MATHA
ACHARYA
SCHOLAR
INSTITUTION
AUTHORIZED_VERIFIER
```

Examples:

```text
Identity verified
Family/reference verified
Madhva affiliation attested
Education attested
Traditional qualification attested
Institutional reference
```

DGE should display:

> Institutionally Attested

only when an actual attestation record exists.

---

# 36. Matrimony authorization rule

The UM app research provides an architectural reference.

DGE should reproduce the **interaction pattern**, not indiscriminately copy protected profile data.

Correct acquisition options:

```text
authorized API
official export
user opt-in import
admin-authorized migration
```

Do not bypass:

- login
- OTP
- subscription controls
- contact gates
- certificate pinning
- device attestation
- access control

If an endpoint requires credentials, Cloud Code must mark it:

```text AUTHORIZATION_REQUIRED
```

and continue with publicly accessible data.

---

# 37. DGE backend architecture

Recommended:

```text
                    DGE FRONTEND
                         |
                  API / Cloud Functions
                         |
        +----------------+----------------+
        |                |                |
  Panchanga API     Institution API   Matrimony API
        |                |                |
        +----------------+----------------+
                         |
                  Canonical Database
                         |
        +----------------+----------------+
        |                |                |
     PostgreSQL      Object Storage    Search Index
        |                |                |
        +----------------+----------------+
                         |
                  Provenance Store
                         |
                 Source Artifact Store
```

Google Cloud/Firebase can be used where appropriate.

For DGE's current environment, a practical split is:

```text
Firebase Authentication
Cloud Functions / Cloud Run
Firestore for app-oriented entities
Cloud Storage for original artifacts/images
Cloud SQL/PostgreSQL for relational Panchāṅga/matching data if scale/query complexity warrants it
```

Do not force everything into Firestore if relational queries become cumbersome.

---

# 38. Source-adapter service

Create a standard interface:

```text
SourceAdapter
-------------
discover()
fetch(year)
fetch(date)
fetch_artifact()
parse()
normalize()
validate()
```

Implementation examples (active — Śrīpādarāja intentionally excluded, see §19):

```text
UttaradiAdapter
SrsAdapter
UdupiAdapter
VishweshaAdapter      (also the Pejāvara Panchāṅga source — no separate PejavaraAdapter, see §14/§18)
SodeAdapter
TithiNirnayaAdapter
VyasarajaAdapter
```

**Not currently instantiated:**

- `PejavaraAdapter` — withdrawn; Pejāvara's Panchāṅga is served by `VishweshaAdapter`. If Pejāvara's *institutional* content (§18) ever needs a dedicated adapter rather than a manual web-acquisition pass, it should be a distinct concern from Panchāṅga, not a Panchāṅga-source duplicate.
- `SripadarajaAdapter` — not built until §19's future-acquisition conditions are met.

---

# 39. Adapter result contract

Every adapter should return:

```json
{
  "source": {},
  "artifacts": [],
  "records": [],
  "entities": [],
  "media": [],
  "warnings": [],
  "validation": {}
}
```

Never let an adapter directly mutate production records without validation.

---

# 40. Annual Panchāṅga ingestion job

Recommended Cloud Scheduler / Cloud Run workflow:

```text
discover source
      ↓
check new year
      ↓
download artifact
      ↓
hash artifact
      ↓
compare previous hash
      ↓
parse
      ↓
normalize
      ↓
validate
      ↓
generate diff
      ↓
human approval if required
      ↓
publish
```

For dynamic APIs:

```text
weekly/monthly refresh
```

For annual PDFs:

```text
annual discovery + manual approval
```

For current daily dynamic sources:

```text
daily or weekly refresh
```

---

# 41. Validation rules for Panchāṅga

At minimum:

### Date completeness

Expected daily coverage must be checked.

### Tithi continuity

Flag impossible/missing transitions.

### Duplicate date records

Flag duplicate `(source, date, language, location)`.

### Language alignment

Verify multilingual records correspond to the same source date.

### Sunrise/sunset sanity

Flag impossible times.

### Festival consistency

Compare source's own event dataset against daily records.

### Ekādaśī consistency

Verify dedicated Ekādaśī dataset agrees with daily Panchāṅga where expected.

### Source hash

Never overwrite an original artifact.

---

# 42. Cross-source comparison

DGE should support comparison without declaring one source "wrong".

Example:

```text
2026-09-XX

Uttaradi:
Tithi = ...

SRS:
Tithi = ...

Sode:
Tithi = ...

Vyasaraja:
Tithi = ...
```

Display:

```text
Source-specific Panchāṅga
```

rather than forcing reconciliation.

---

# 43. Cloud Code "APK Archaeologist"

Implement an orchestrator with this workflow:

```text
INPUT
  APK + institution + app name + version
        |
        v
[1] IDENTIFY
        |
        v
[2] STATIC EXTRACT
        |
        v
[3] FRAMEWORK DETECT
        |
        +---- Flutter
        |       |
        |       +-- locate AOT
        |       +-- inspect assets
        |
        +---- React Native
        |       |
        |       +-- inspect JS bundle
        |
        +---- Native
        |       |
        |       +-- inspect DEX/network
        |
        +---- B4A
                |
                +-- inspect BAL/VSS/TXT/XLSX
        |
        v
[4] NETWORK DOMAIN DISCOVERY
        |
        v
[5] RUNTIME
        |
        v
[6] CONTENT DISCOVERY
        |
        v
[7] DATA EXTRACTION
        |
        v
[8] NORMALIZATION
        |
        v
[9] PROVENANCE
        |
        v
[10] VALIDATION REPORT
        |
        v
[11] DGE IMPORT PACKAGE
```

---

# 44. Automated content discovery prompts

For an app, Cloud Code should actively search the UI for:

```text
Panchanga
Calendar
Tithi
Ekadashi
Festival
Aradhana
Parampara
Mutt
Matha
Deities
Pratima
Moola
Sthana
History
Branches
Kshetra
Publications
Events
Seva
Gallery
Photos
Contact
```

Language variants should be included:

```text
Kannada
Sanskrit
Telugu
Tamil
Hindi
English
```

---

# 45. UI crawling strategy

For each discovered section:

```text
open
screenshot
dump UI hierarchy
record navigation path
record URL/API requests
save page data
save images
save source reference
```

For list pages:

```text
enumerate all items
open each item
extract full detail
return
continue
```

For hierarchical pages:

```text
build parent-child relationships
```

This is essential for Paramparā and deity trees.

---

# 46. Image acquisition strategy

When an image is loaded:

1. capture original URL if available;
2. preserve original response;
3. save source artifact;
4. compute hash;
5. create thumbnail;
6. associate image with entity;
7. retain source provenance.

Do not rely solely on screenshots when the application exposes the original image URL.

---

# 47. Web fallback

If the app is only a wrapper around the official website:

```text
detect WebView URL
        ↓
crawl official website directly
        ↓
prefer structured HTML/API/JSON
        ↓
extract images
        ↓
preserve canonical URL
```

Sode 3.3 is a strong example where current official website content may now be richer than the legacy APK.

---

# 48. Source rights / licensing

Create:

```text
source_rights
-------------
source_id
rights_status
license
permission_contact
attribution_required
redistribution_allowed
derivative_allowed
personal_data
notes
```

Possible statuses:

```text
PUBLIC_OFFICIAL
OFFICIAL_WITH_TERMS
PERMISSION_REQUIRED
USER_CONTRIBUTED
PERSONAL_DATA
UNKNOWN
RESTRICTED
```

Do not publish material merely because it was technically extractable.

---

# 49. Matrimony privacy architecture

Sensitive fields:

```text
phone
whatsapp
email
DOB
address
family details
photos
identity documents
verification records
```

Use:

```text
field-level authorization
encrypted storage
audit logs
data deletion
consent history
visibility rules
rate limiting
abuse reporting
```

Never put private contact information into a public search index.

---

# 50. DGE search index

Searchable institutional fields:

```text
Mutt
Acharya
Deity
Pratima
Kshetra
Branch
Festival
Panchanga
Publication
Event
```

Matrimonial search must be a separate permission-aware index.

---

# 51. Search result provenance

Every result should be able to answer:

> Where did this come from?

Example:

```text
Sri Bhuvaraha
Source:
Sri Sode Vadiraja Matha official website
Page:
Daily Worship
Retrieved:
2026-09-11
```

For APK:

```text
Source:
Uttaradi Matha app
Version:
1.9.0
Artifact:
um_app_seed.db
Table:
main_deities_table
Record:
id=...
```

---

# 52. DGE source record

```text
source_artifact
---------------
id
institution
application
package_name
version
source_type
original_url
retrieval_method
retrieved_at
sha256
content_type
local_storage_key
rights_status
```

---

# 53. Research report produced per APK

Cloud Code must produce:

```text
APK_REPORT.md
```

with:

1. identity
2. framework
3. version
4. package
5. static assets
6. databases
7. URLs
8. network findings
9. runtime findings
10. Panchāṅga architecture
11. institutional content
12. media content
13. API schema
14. acquisition method
15. authorization requirements
16. confidence
17. unresolved questions
18. recommended DGE adapter

---

# 54. Import package produced per source

```text
source-import/
  manifest.json
  raw/
  normalized/
    panchanga.json
    institutions.json
    deities.json
    parampara.json
    branches.json
    events.json
    publications.json
  media/
  validation/
  provenance/
```

---

# 55. Human review workflow

Cloud Code should NOT silently publish uncertain data.

Create queues:

```text
NEW
AUTO_VALIDATED
NEEDS_REVIEW
CONFLICT
DUPLICATE
RIGHTS_REVIEW
PUBLISHED
RETRACTED
```

A human reviewer can approve a complete import.

---

# 56. What should be fully automated

Automate:

- APK extraction
- framework detection
- URL discovery
- asset inventory
- DB discovery
- JSON discovery
- text extraction
- image hashing
- PDF archiving
- API schema discovery
- runtime navigation
- screenshot capture
- source hashing
- date coverage checks
- duplicate detection
- diff reports
- import-package generation

---

# 57. What should remain human-controlled

Human approval should remain for:

- rights/redistribution decision
- institutional identity mapping
- theological interpretation
- conflicting source resolution
- official attestation
- matrimonial verification
- publication of sensitive personal data
- major corrections to source-derived text

---

# 58. Immediate execution order

## Phase 1 — finish APK archaeology

Priority (Śrīpādarāja and Pejāvara removed as separate active items — see below):

1. Udupi
2. Vishwesha (this covers Pejāvara's Panchāṅga — no separate Pejāvara APK item)
3. SRS Panchanga 2.0.0
4. Uttarādi
5. Tithi Nirṇaya
6. Vyāsarāja
7. Sode 3.3

**Not scheduled in Phase 1:**

- Pejāvara — its Panchāṅga is item 2 above; its institutional-knowledge acquisition (§18) is a website pass, not APK archaeology, and can proceed independently whenever convenient.
- Śrīpādarāja — deferred entirely until §19's conditions are met (a confirmed, accessible app or website). Do not obtain or analyze an APK for it under the current inventory.

---

## Phase 2 — build source adapters

First:

```text
UttaradiAdapter
SRSAdapter
UdupiAdapter
VishweshaAdapter
```

Then:

```text
SodeAdapter
TithiNirnayaAdapter
VyasarajaAdapter
```

**Not built in this phase or the next:** `PejavaraAdapter` (withdrawn, see §14/§38) and `SripadarajaAdapter` (deferred, see §19/§38).

---

# 59. Phase 3 — institutional graph

Build:

```text
Matha
Acharya
Parampara
Deity
Pratima
Branch
Kshetra
Event
Publication
Festival
```

and populate the first institutions.

---

# 60. Phase 4 — Panchāṅga archive

Build:

```text
year registry
source archive
normalized daily records
source comparison
```

Target:

> Every supported institution × every obtainable year.

---

# 61. Phase 5 — matrimonial subsystem

Build only after:

```text
authentication
consent
privacy
verification
contact gating
```

are defined.

Then:

```text
profile
photo
search
match
interest
invitation
mutual acceptance
communication
attestation
```

---

# 62. Current source map

## Uttarādi

Primary discovered structured source:

```text
um_app_seed.db
```

Annual PDF CDN:

```text
cdn.umath.in
```

## SRS

Current packaged structured source:

```text
panchanga.en.json
aradhana.json
ekadashi.json
festivals.json
tarpana.json
```

Legacy update endpoint observed in older APK:

```text
https://srsmatha.org/srsapp/dbupd.php
```

Official web source:

```text
https://srsmatha.org/panchanga.php
```

## Sode

Official current website:

```text
https://www.sodematha.in/
```

Important pages:

```text
/parampara.html
/dailyworship.html
/branch.html
/sode.html
```

Legacy app contains corresponding website/API references.

## Vishwesha (= Pejāvara Panchāṅga)

Panchāṅga source: Vishwesha Panchanga V.26 (B4A app, §14). One source, one adapter — see §38.

Pejāvara Maṭha institutional knowledge (separate from Panchāṅga, §18):

```text
https://pejavaramatha.in/
```

## Śrīpādarāja

**Future target only — status NOT_YET_ACQUIRED (see §19).** No app or website currently confirmed available to us. Unconfirmed leads from earlier research, not to be acted on until reconfirmed:

```text
possible website: https://www.sripadarajamutt.org/
possible historical Android package: com.ssprm.sspmuser
```

## Tithi Nirṇaya

Official app listing identifies:

```text
com.krishna.panchanga_app
```

and its Sode Vādirāja / Āryabhaṭa Siddhānta identity.

---

# 63. Important correction to earlier research

The investigation has now established that some apps previously described only as "possibly pre-curated" are actually demonstrably pre-curated in the supplied APK:

### Definitively packaged/pre-curated

```text
Uttarādi
SRS Panchanga 2.0.0
Udupi Panchanga
Vishwesha Panchanga
```

### Strongly suggests server/cache model, exact endpoint pending

```text
Vyāsarāja
```

### Server/web-backed institutional app with explicit endpoints

```text
Sode 3.3
```

### Unresolved because supplied Flutter payload is incomplete

```text
Tithi Nirṇaya
```

This classification must be reflected in the implementation.

---

# 64. Important observation about annual data

The fact that a current APK contains data for one or more years does NOT mean DGE should depend on the APK for every future year.

The correct model is:

```text
APK analysis
      ↓
discover source-generation/acquisition mechanism
      ↓
identify official annual source
      ↓
automate annual ingestion
```

For packaged annual data:

```text
new app version
      ↓
new assets
      ↓
extract next year
```

For API:

```text
year parameter
      ↓
download directly
```

For PDF:

```text
official annual PDF
      ↓
archive + parse
```

---

# 65. Cloud Code completion criterion

The task is complete only when Cloud Code can answer for each target institution:

### Panchāṅga

```text
Where does the data come from?
How is it generated?
What years are available?
How do we acquire a new year?
What fields exist?
What location/methodology is used?
```

### Institutional knowledge

```text
What is the Paramparā?
What are the Mūla Pratimās?
What are the Sthāna Pratimās?
What branches exist?
What images exist?
What descriptions exist?
What are the official sources?
```

### Matrimony

```text
What profile data exists?
How is matching implemented?
How does invitation/interest work?
When is contact revealed?
What verification exists?
What is user-controlled?
What data is public/private?
```

---

# 66. Acceptance tests for Cloud Code

A successful run should produce:

```text
✓ APK identified
✓ framework identified
✓ source artifacts enumerated
✓ local databases identified
✓ URLs identified
✓ network endpoints identified where observable
✓ runtime UI mapped
✓ Panchāṅga source classified
✓ institutional content classified
✓ images extracted/indexed
✓ provenance recorded
✓ rights status recorded
✓ unresolved items listed
✓ DGE import package generated
```

For a source that cannot be fully inspected:

```text
✓ limitation explicitly documented
✓ no unsupported inference
✓ next acquisition action identified
```

---

# 67. Security and ethics rule

The project is for DGE's legitimate research and integration.

Cloud Code must not:

- bypass authentication
- steal session tokens
- circumvent payment
- defeat DRM
- defeat device attestation
- defeat access controls
- expose private matrimonial data
- publish phone numbers without consent
- scrape private profiles indiscriminately

The objective is:

> **authorized acquisition and source preservation, not security circumvention.**

---

# 68. Recommended final DGE UI

## Panchāṅga

```text
Panchāṅga
 ├── Select Maṭha
 ├── Select Year
 ├── Select Location
 ├── Select Language
 └── Calendar
       └── Daily detail
```

Example:

```text
Uttarādi Maṭha Panchāṅga
2026–27
Mysuru
Kannada
```

and:

```text
Sode Vādirāja Maṭha
2026–27
Udupi
Kannada
```

remain separate sources.

---

# 69. Mutt page

```text
Sri Sode Vadiraja Matha
|
+-- Overview
+-- Parampara
+-- Deities
|    +-- Moola
|    +-- Sthana
|    +-- Other
+-- Branches
+-- Kshetras
+-- Panchanga
+-- Festivals
+-- Events
+-- Publications
+-- Gallery
+-- Contact
```

---

# 70. Deity page

```text
Sri Bhuvaraha

[PHOTO]

Type:
Presiding deity / Parampara deity

Description:
[Source-derived description]

Historical origin:
[Source-derived]

Worship:
[Source-derived]

Associated Matha:
Sri Sode Vadiraja Matha

Source:
[Official source]

Verified:
[status]
```

---

# 71. Matrimony UI

```text
Matrimony
|
+-- Browse
+-- Search
+-- Recommended Matches
+-- Shortlisted
+-- Express Interest
+-- Inbox
|    +-- Received
|    +-- Sent
+-- Mutual Connections
+-- Verified / Attested
+-- My Profile
+-- Privacy & Contact Settings
```

---

# 72. Long-term DGE advantage

This architecture allows DGE to become a **federated Madhva knowledge layer**.

It does not need to replace each institution's systems.

Instead:

```text
Mutt
  ↓
Official digital source
  ↓
DGE provenance-preserving ingestion
  ↓
Unified discovery
```

The original institution remains the authority.

DGE becomes the interoperable discovery and knowledge layer.

---

# 73. Recommended next action for Cloud Code

Give Cloud Code:

1. this document;
2. all supplied APKs (Udupi, Vishwesha, SRS Panchanga 2.0.0 and legacy 2.0, Uttarādi, Tithi Nirṇaya, Vyāsarāja, Sode 3.3 — **not** Pejāvara or Śrīpādarāja, per the corrections above);
3. extracted UM Matrimony bundle/Dex files;
4. any future APKs for additional Madhva Maṭhas as they are confirmed acquirable — Śrīpādarāja only once §19's conditions are met, and no separate Pejāvara APK is needed at all (§14/§18);
5. permission to create a disposable Android analysis environment;
6. permission to use official/public network endpoints;
7. credentials only where the owner explicitly authorizes them.

Then instruct:

> "Execute the APK Archaeologist workflow for every supplied application. Do not merely describe what could be done. Produce actual source reports, artifacts, endpoint inventories, structured extraction candidates, and DGE import packages. Continue until every obtainable source is classified as API, database, packaged data, PDF, website, or unresolved."

---

# 74. Final implementation principle

The most important design rule for DGE is:

> **Acquire once, preserve forever, normalize carefully, cite everything, and never erase source identity.**

Panchāṅga differences are data, not errors.

Institutional differences are data, not inconsistencies.

Multiple images are provenance opportunities, not duplication.

Matrimonial verification is an attestation system, not a checkbox.

And APKs are not merely applications to reverse engineer; they are **containers of institutional digital knowledge** that can reveal databases, annual calendars, images, descriptions, APIs, and source relationships.

A closely related rule, added by the 11 Sep 2026 correction: **one institutional/source adapter per actual data source.** An institution's name and a product's name are not proof of two sources — check before registering a second adapter.

---

# 75. External research references

These are useful official/public starting points for Cloud Code validation:

- SRS Matha Panchanga: https://srsmatha.org/panchanga.php
- SRS Matha official site: https://srsmatha.org/
- SRS Matha Panchanga Play listing: https://play.google.com/store/apps/details?id=com.panchanga
- Tithi Nirṇaya Play listing: https://play.google.com/store/apps/details?id=com.krishna.panchanga_app
- Sode Matha official site: https://www.sodematha.in/
- Sode Daily Worship / Deities: https://www.sodematha.in/dailyworship.html
- Sode Parampara: https://www.sodematha.in/parampara.html
- Sode Branches: https://www.sodematha.in/branch.html
- Pejāvara Matha: https://pejavaramatha.in/ (institutional knowledge only — Panchāṅga is Vishwesha, §14/§18)
- Pejāvara Matha information: https://pejavaramatha.in/pejavara-matha/
- Śrīpādarāja Matha: https://www.sripadarajamutt.org/ (unconfirmed — reference only, not an active source; see §19)
- Playwright Android API: https://playwright.dev/docs/api/class-android
- Playwright network interception: https://playwright.dev/docs/network
- Flutter Android deployment: https://docs.flutter.dev/deployment/android
- Flutter deferred components: https://docs.flutter.dev/perf/deferred-components

---

# 76. End state

The desired end state is:

```text
                         DGE
                          |
       +------------------+------------------+
       |                  |                  |
   PANCHANGA          INSTITUTIONS       MATRIMONY
       |                  |                  |
       |              +---+---+              |
       |              |       |              |
    Mutt/year       Matha   Deity         Profiles
    location        Guru    Pratima       Matching
    language        Branch  Photo         Interest
    source          Kshetra History       Attestation
       |              |       |              |
       +--------------+-------+--------------+
                          |
                    PROVENANCE LAYER
                          |
                Original Source Artifacts
                          |
             APK / API / DB / JSON / PDF
                          |
                   SOURCE AUTHORITY
```

Cloud Code's role is to turn this architecture into an **actual continuously maintainable acquisition and ingestion system**, rather than leaving the project dependent on manual APK inspection.

**End of specification.**
