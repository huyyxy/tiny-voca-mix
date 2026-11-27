// Retire the offline synthesizer installed by earlier Pages releases.
self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil((async () => {
  const prefix = 'vivian-pages-' + self.registration.scope + '-';
  const keys = await caches.keys();
  await Promise.all(keys.filter(key => key.startsWith(prefix)).map(key => caches.delete(key)));
  await self.registration.unregister();
})()));
