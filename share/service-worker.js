const CACHE_NAME = 'stagedesk-share-v66'
const APP_SHELL = [
  '/share/',
  '/share/service-worker.js',
  '/share-assets/share.css?v=20260721-66',
  '/share-assets/share.js?v=20260721-66',
  '/assets/stagedesk-pro-icon.png',
]

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting()),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const request = event.request
  const url = new URL(request.url)
  if (request.method !== 'GET' || url.origin !== self.location.origin) return

  if (request.mode === 'navigate' && url.pathname.startsWith('/share/')) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone()
          void caches.open(CACHE_NAME).then((cache) => cache.put('/share/', copy))
          return response
        })
        .catch(() => caches.match('/share/')),
    )
    return
  }

  const isAppAsset = url.pathname.startsWith('/share-assets/') || url.pathname.startsWith('/share/') || url.pathname === '/assets/stagedesk-pro-icon.png'
  if (!isAppAsset) return

  event.respondWith(
    caches.match(request).then((cached) => cached || fetch(request).then((response) => {
      const copy = response.clone()
      void caches.open(CACHE_NAME).then((cache) => cache.put(request, copy))
      return response
    })),
  )
})
