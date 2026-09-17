// DGE Service Worker — minimal offline app-shell support.
//
// Phase 7 of the mobile UI overhaul: an ashtadhyayi.com-inspired "Offline
// Mode" the project lead asked to add, confirmed via investigation to not
// exist anywhere in this repo yet (no sw.js, no manifest.json, no
// navigator.serviceWorker.register call).
//
// Deliberately no fixed precache list. This repo's own scripts are
// cache-busted with a per-file ?v=... query param that changes on nearly
// every edit (see index.html's <script src="js/....js?v=..."> tags) — a
// hardcoded install-time asset list here would silently drift out of sync
// the next time any one file's version bumped, serving a stale JS file
// alongside a fresh HTML. Runtime network-first caching avoids that
// entirely: every same-origin GET that succeeds online is cached under
// its own real (including querystring) URL, and only served from that
// cache when the network fails. The tradeoff: a page/asset never opened
// before still needs a connection the first time — a normal, honest
// limitation of "what you've visited becomes available offline," not
// full offline browsing of the whole corpus sight unseen.
const CACHE_NAME = 'dge-runtime-v1';

self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((k) => k.startsWith('dge-runtime-') && k !== CACHE_NAME).map((k) => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return; // only GETs are meaningfully cacheable/replayable

  const url = new URL(req.url);
  // Cross-origin requests (jsDelivr search index, archive.org audio, Google
  // Fonts, Firebase, etc.) are left completely untouched -- intercepting
  // them risks opaque-response caching pitfalls and duplicates caching the
  // 330 MB search index/audio files already handle themselves elsewhere
  // (see global-search.js/audio.js's own Cache API usage).
  if (url.origin !== self.location.origin) return;

  event.respondWith(
    fetch(req).then((res) => {
      // Network-first: an online reader always gets the freshest content;
      // the cache is purely a fallback for when the network fails, never
      // preferred over it. Only a genuinely successful response is cached,
      // so a 404/500 never gets "frozen in" as the offline answer.
      if (res && res.ok) {
        const resClone = res.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(req, resClone)).catch(() => {});
      }
      return res;
    }).catch(() => caches.match(req).then((cached) => cached || Promise.reject(new Error('offline and not cached: ' + req.url))))
  );
});
