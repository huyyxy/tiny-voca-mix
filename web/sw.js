// The Pages build replaces these with the hash and file sizes of this release.
const prefix = 'vivian-pages-' + self.registration.scope + '-';
const cacheName = prefix + '__VERSION__';
const sizes = /* FILE SIZES */ {};
const urls = new Set(Object.keys(sizes).map(path => new URL(path, self.registration.scope).href));
const index = new URL('index.html', self.registration.scope).href;
const total = Object.values(sizes).reduce((sum, size) => sum + size, 0);
let received = 0;
let lastReport = -Infinity;

function progress() {
  return {type: 'download-progress', received, total};
}

async function reportProgress(force = false) {
  const now = performance.now();
  if (!force && now - lastReport < 120) return;
  lastReport = now;
  const clients = await self.clients.matchAll({type: 'window', includeUncontrolled: true});
  for (const client of clients) {
    if (client.url.startsWith(self.registration.scope)) client.postMessage(progress());
  }
}

// A second tab may join an installation after the download has already started.
self.addEventListener('message', event => {
  if (event.data?.type === 'get-download-progress') event.source?.postMessage(progress());
});

async function cacheFile(cache, url, signal) {
  const response = await fetch(url, {cache: 'reload', signal});
  if (!response.ok || !response.body) throw Error('Download failed: ' + url);
  const reader = response.clone().body.getReader();
  // Count decoded bytes as they arrive, while Cache Storage writes the original response.
  async function countBytes() {
    for (;;) {
      const {done, value} = await reader.read();
      if (done) return;
      received += value.byteLength;
      await reportProgress();
    }
  }
  await Promise.all([cache.put(url, response), countBytes()]);
}

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(cacheName);
    const abort = new AbortController();
    try {
      await Promise.all([...urls].map(url => cacheFile(cache, url, abort.signal)));
      await reportProgress(true);
    } catch (error) {
      abort.abort();
      await caches.delete(cacheName);
      throw error;
    }
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) {
      if (key.startsWith(prefix) && key !== cacheName) await caches.delete(key);
    }
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  url.search = '';
  const key = url.href === self.registration.scope ? index : url.href;
  if (!urls.has(key)) return;
  event.respondWith((async () => {
    const cache = await caches.open(cacheName);
    return await cache.match(key) || fetch(event.request);
  })());
});
