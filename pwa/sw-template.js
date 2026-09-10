/* Generated with content hashes. Never edit the emitted sw.js by hand. */
const RELEASE = __RELEASE__;
const FILES = __FILES__;
const ROOT = new URL('./', self.registration.scope);
// Separate apps installed under different paths on the same origin.
const PREFIX = 'essaylab-pwa:' + encodeURIComponent(ROOT.pathname) + ':';
const CACHE = PREFIX + 'release:' + RELEASE;
const META = PREFIX + 'clients';
const MARKER = new URL('__essaylab_complete__', ROOT).href;
const ACTIVATED = new URL('__essaylab_activated__', ROOT).href;
const CREATED = new URL('__essaylab_created__', ROOT).href;
const ACTIVE = new URL('__essaylab_active__', ROOT).href;
const entries = new Map(FILES.map(file => [new URL(file.url, ROOT).href, file]));
const absolute = path => new URL(path, ROOT).href;
let lastCheck = 0;

async function checkedFetch(url, expected) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch(url, {cache: 'no-store', credentials: 'same-origin', signal: controller.signal});
    if (!response.ok || response.redirected || response.type === 'opaque') throw new Error('Incomplete release: ' + url);
    const bytes = await response.clone().arrayBuffer();
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    const hash = [...new Uint8Array(digest)].map(n => n.toString(16).padStart(2, '0')).join('');
    if (hash !== expected) throw new Error('Release hash mismatch: ' + url);
    return response;
  } finally { clearTimeout(timer); }
}

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    try {
      await cache.put(CREATED, new Response(String(Date.now())));
      // Bounded downloads; wait for every worker before deleting a failed stage.
      let next = 0;
      const downloads = Array.from({length: 6}, async () => {
        while (next < FILES.length) {
          const file = FILES[next++], url = absolute(file.url);
          await cache.put(url, await checkedFetch(url, file.sha256));
        }
      });
      const results = await Promise.allSettled(downloads);
      const failure = results.find(result => result.status === 'rejected');
      if (failure) throw failure.reason;
      await cache.put(MARKER, new Response(RELEASE));
      // Safe because all dependencies have release-specific URLs. No page reload.
      await self.skipWaiting();
    } catch (error) {
      await caches.delete(CACHE);
      throw error;
    }
  })());
});

async function cleanup() {
  const clients = await self.clients.matchAll({type: 'window', includeUncontrolled: true});
  const ours = clients.filter(client => client.url.startsWith(ROOT.href));
  const meta = await caches.open(META);
  if (await (await meta.match(ACTIVE))?.text() !== RELEASE) return;
  const keep = new Set([CACHE]);
  let unknown = false;
  for (const client of ours) {
    const record = await meta.match(absolute('__client__/' + client.id));
    if (record) keep.add(PREFIX + 'release:' + await record.text());
    else unknown = true;
  }
  const ids = new Set(ours.map(client => absolute('__client__/' + client.id)));
  for (const request of await meta.keys()) if (request.url !== ACTIVE && !ids.has(request.url)) await meta.delete(request);
  // Until existing windows announce their release, do not evict their lazy images.
  if (unknown) return;
  const names = (await caches.keys()).filter(name => name.startsWith(PREFIX + 'release:'));
  for (const name of names) {
    if (keep.has(name)) continue;
    // An old worker must not delete a new worker's in-progress installation.
    if (await (await meta.match(ACTIVE))?.text() !== RELEASE) return;
    const cache = await caches.open(name);
    if (!await cache.match(ACTIVATED)) {
      const created = Number(await (await cache.match(CREATED))?.text());
      if (!created || Date.now() - created < 86400000) continue;
    }
    await caches.delete(name);
  }
}
let housekeeping = Promise.resolve();
function scheduleCleanup() {
  housekeeping = housekeeping.catch(() => {}).then(cleanup);
  return housekeeping;
}

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    await (await caches.open(META)).put(ACTIVE, new Response(RELEASE));
    await (await caches.open(CACHE)).put(ACTIVATED, new Response('true'));
    await self.clients.claim();
    const clients = await self.clients.matchAll({type: 'window'});
    for (const client of clients) if (client.url.startsWith(ROOT.href)) client.postMessage({type: 'REQUEST_RELEASE'});
    await scheduleCleanup();
  })());
});

self.addEventListener('message', event => {
  if (event.data?.type !== 'CLIENT_RELEASE' || !/^[a-f0-9]{20}$/.test(event.data.release) || !event.source?.id) return;
  event.waitUntil((async () => {
    const client = await self.clients.get(event.source.id);
    if (!client || !client.url.startsWith(ROOT.href)) return;
    const meta = await caches.open(META);
    await meta.put(absolute('__client__/' + client.id), new Response(event.data.release));
    const cache = await caches.open(CACHE);
    if (await cache.match(MARKER)) client.postMessage({type: 'OFFLINE_READY', release: RELEASE});
    await scheduleCleanup();
  })());
});

async function revalidateRelease() {
  if (Date.now() - lastCheck < 60000) return;
  lastCheck = Date.now();
  try { await self.registration.update(); } catch { lastCheck = 0; }
}

async function fromRelease(url) {
  const file = entries.get(url);
  if (file) {
    const cache = await caches.open(CACHE);
    const hit = await cache.match(url);
    if (hit) return hit;
    // Recover an individually evicted item only if its bytes still match this release.
    try {
      const response = await checkedFetch(url, file.sha256);
      await cache.put(url, response.clone());
      return response;
    } catch { return null; }
  }
  // Live old pages keep requesting their own immutable URLs after worker activation.
  for (const name of await caches.keys()) {
    if (!name.startsWith(PREFIX + 'release:')) continue;
    const hit = await (await caches.open(name)).match(url);
    if (hit) return hit;
  }
  return null;
}

async function navigate(request) {
  const url = new URL(request.url);
  if (url.pathname !== ROOT.pathname && url.pathname !== new URL('index.html', ROOT).pathname) {
    // All UI routes currently live in one document. Redirect ensures relative paths work.
    return Response.redirect(ROOT.href, 302);
  }
  const page = await fromRelease(absolute('index.html'));
  if (page) return page;
  const fallback = await fromRelease(absolute('offline.html'));
  return fallback || new Response('<!doctype html><meta charset="utf-8"><title>EssayLab</title><p>本地资料未准备完整，请联网后重新打开 EssayLab。</p>', {
    status: 503, headers: {'Content-Type': 'text/html; charset=utf-8'}
  });
}

self.addEventListener('fetch', event => {
  const request = event.request, url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== ROOT.origin || !url.href.startsWith(ROOT.href)) return;
  if (request.mode === 'navigate') {
    // Stale-while-revalidate at release level, not independently for interdependent JSON.
    event.respondWith(navigate(request));
    event.waitUntil(revalidateRelease());
    return;
  }
  if (url.pathname === new URL('sw.js', ROOT).pathname) return;
  url.search = ''; url.hash = '';
  if (!entries.has(url.href) && !url.pathname.startsWith(new URL('releases/', ROOT).pathname)) return;
  event.respondWith((async () => {
    const response = await fromRelease(url.href);
    if (response) return response;
    if (entries.has(url.href)) return new Response('', {status: 503, statusText: 'Release verification failed'});
    // Never substitute HTML for failed JSON, fonts, scripts or images; never cache errors.
    try { return await fetch(request); }
    catch { return new Response('', {status: 503, statusText: 'Offline resource unavailable'}); }
  })());
  if (entries.has(url.href) && !url.pathname.includes('/releases/')) event.waitUntil(revalidateRelease());
});
