# The search index: how long it takes, who publishes it, who may read it

Written 22 Sep 2026, answering six questions asked directly.

## 1. How long a re-index takes — measured, not estimated

From `reindex.yml` run `35705512268`, the first run that both built and
published successfully:

| step | time |
|---|---|
| checkout | 2.4 min |
| **rebuild the index** | **12.7 min** |
| refresh the library-status snapshot | 0.2 min |
| **publish to Cloud Storage** | **21.9 min** |
| checkout BrahmaBuddhi | 0.2 min |
| **total** | **37.9 min** |

Earlier successful runs that rebuilt but did not publish took 15.2 and
16.4 min, which agrees: **build ≈ 13–16 min, publish ≈ 22 min.**

The publish is slower than the build because it is 215,933 separate small
files, not 1.9 GB of throughput. `gcloud storage rsync` reported
`Average throughput: 1.6MiB/s` — that is per-object overhead, not bandwidth.
The fix, if this ever needs to be faster, is fewer and larger shards, not a
bigger machine.

For comparison, `deploy-firestore.yml` finishes in about 1 minute.

## 2. Did the whole 1.9 GB have to be pushed just to prove it worked?

**No, and this is a fair criticism.** What the first successful publish was
actually proving was four things, every one of which a single 12-byte file
would have proven:

* `SEARCH_INDEX_BUCKET` holds a valid bucket name (it had held an invalid one);
* the service account key in `FIREBASE_SERVICE_ACCOUNT` activates;
* that account can write to `gs://sarvamula-search-index`;
* `allUsers` can read the object back over HTTPS.

Running the whole rsync to establish that cost ~22 minutes of runner time and
an egress bill for content that was going to be re-uploaded anyway. A
`gcloud storage cp` of one probe file, then `curl` on its public URL, answers
all four in about five seconds.

`reindex.yml` now has a **`probe`** input that does exactly that. Ticked, the
run skips the gate, the build and the publish, writes one twelve-byte object,
fetches it back anonymously over HTTPS, deletes it, and stops — seconds, not
forty minutes. It fails with a specific message for each of the four things it
checks, including the one that is easy to miss: an object that writes fine but
returns 403 to an anonymous read means `allUsers` is missing Storage Object
Viewer, i.e. the index would be published and unreadable.

Run it with `probe` ticked after any change to the bucket, its permissions,
`SEARCH_INDEX_BUCKET`, or the service account — before committing half an hour
of runner time to a real publish.

The full publish was not *wasted* — that build is the one now serving at
`search_index/449134cbc285/` — but it was not the right way to test.

## 3. Can the index be published from ShriBuddhi and consumed elsewhere?

**Yes, and that is already how it works.** The bucket is not owned by a repo.
`reindex.yml` runs on ShriBuddhi, authenticates as
`github-search-index@sarvamula-org`, and writes to
`gs://sarvamula-search-index`. Anything that can make an HTTPS request —
JagatTest, BrahmaBuddhi, the live site at sarvamula.org, a new repo created
tomorrow — reads the same URL:

    https://storage.googleapis.com/sarvamula-search-index/search_index/<build>/

One publisher, many consumers, one copy of the data. **No repository needs its
own index, its own bucket, or its own build.** A second repo that wants to
search reads that URL; it does not re-run `reindex.yml`.

The site chooses its index through one string, `appConfig.searchIndexBase` in
`js/config.js`, with `window.DGE_SEARCH_INDEX` as the per-reader override.
Repointing every site at a new build is one line.

## 4. GCS versus jsDelivr — why both exist

They are two delivery routes for the same files, and **the live site is still
on the old one**.

* **jsDelivr** (`cdn.jsdelivr.net/gh/…@<sha>/`) serves files straight out of a
  git branch. It is free and globally cached. Its cost is that publishing means
  *committing 1.9 GB into git*, which is why ShriBuddhi's repository is now
  2.6 GB, and that jsDelivr caches a `@branch` URL for ~12 hours — so the pin
  must be a commit SHA, and a republish changes nothing for readers until that
  SHA is edited into `js/config.js` by hand.
* **Cloud Storage** serves the same tree from `gs://sarvamula-search-index`
  with `cache-control: public, max-age=31536000, immutable`. Publishing does
  not touch git at all. The path already contains a build hash, so a new build
  is a new path and there is no stale-cache problem.

Today `js/config.js` still pins
`…bhumandala@838335f8152654c37ee1c256c36b6ff6aab3927f`, the build of
**11 Sep**. The 22 Sep build sits in GCS, complete and publicly readable, and
**no reader is using it yet.** Switching is one line:

    searchIndexBase: "https://storage.googleapis.com/sarvamula-search-index/search_index/449134cbc285",

That switch is worth making deliberately, with a real browser query checked
before and after, because it changes what every reader downloads.

## 5. Why the index grew

It did not grow the way `du` suggests. True content:

| | 11 Sep | 22 Sep | change |
|---|---|---|---|
| content bytes | 1,891 MB | 1,933 MB | **+2.2%** |
| granthas | 1,232 | 1,267 | +2.8% |
| units | 581,064 | 599,749 | +3.2% |

`du` reports 2,680 MB because 179,514 of the files are smaller than one 4 KB
filesystem block — 591 MB of the figure is block slack, not data. The index
grew in step with the corpus.

No record of the index exists earlier than 11 Sep anywhere reachable —
`search-dist` was force-pushed to a single commit and its history is gone — so
the remembered "500 MB" cannot be checked. It is not explained here because it
cannot be, honestly.

## 6. Scholar review in BrahmaBuddhi, and how corrections reach search

The index is built from content, so a correction reaches readers only when a
new index is built and then pinned:

1. A scholar corrects a text in **BrahmaBuddhi**.
2. The correction is merged back into **ShriBuddhi**'s `data/`, which is the
   source `build_search_index.py` reads. *(Today this leg is hand-carried:
   `push-to-brahmabuddhi.yml` relays only a marker file. Content propagation
   is still a stub — see REPO_INVENTORY.md.)*
3. `reindex.yml` runs on ShriBuddhi → ~13 min build, ~22 min publish, new
   build hash.
4. `searchIndexBase` is pointed at the new hash and the site repos are synced.

So the turnaround from an approved correction to a searchable correction is
roughly **40 minutes of machine time plus one deliberate line change** — not
instant, and not automatic. That is by design: an immutable, hash-addressed
build cannot half-publish.

## 7. Restricting search to registered users, and hiding results from some users

Two different questions with two different answers.

**As it stands today, neither is possible.** The index is static files in a
bucket with `allUsers → Storage Object Viewer`. The browser fetches shards
directly. There is no server in the path to ask who is asking, so any
"members only" check in the page is decoration — the URLs are public and can
be fetched with `curl`.

**The project already has the right mechanism, built for the corpus rather
than for search.** `js/config.js` documents `corpusBase`: set it to the
`corpusFile` Cloud Function and every text read goes through an authenticated
proxy that "sends the caller's Firebase ID token, resolves their stored role,
applies the same shelf and gates the reader applies, and streams the file from
a PRIVATE bucket. That is the difference between 'the site does not show this
text' and 'this text cannot be fetched'." Roles already exist in Firestore and
are enforced by `firestore.rules`. `corpusFile` is written but **not deployed**
(it answers 404 today).

Applying the same pattern to search means:

* **Registered-users-only search** — remove `allUsers` from the bucket, add a
  `searchShard` function alongside `corpusFile` that verifies the Firebase ID
  token and streams the shard. Cost: every shard fetch becomes a function
  invocation, and a single query already fans out across many shards. Cheaper
  variant: keep the static bucket but make it private and have a function mint
  short-lived signed URLs for a verified caller.
* **Different results for different users** — this cannot be done by filtering
  in the browser, for the same reason: whoever holds the shard holds
  everything in it. It has to be either (a) filtered server-side, with the
  function dropping hits the caller's role may not see before responding, or
  (b) partitioned at build time into per-role index sets, which multiplies
  build time and storage but keeps serving static and free.

(a) is the honest one and matches how the corpus proxy already works. (b) is
cheaper to serve and leaks whatever the partition boundaries themselves reveal.

Either is a real project, not a setting to toggle. Nothing is half-enabled
today: search is fully public, and the page should not imply otherwise.
