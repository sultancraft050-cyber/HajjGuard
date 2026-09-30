const CACHE = 'hajjguard-public-v2';
const CORE = ['/static/pwa/offline.html', '/manifest.webmanifest'];
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(CORE)).then(() => self.skipWaiting())));
self.addEventListener('activate', event => event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('hajjguard-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim())));
self.addEventListener('fetch', event => {
 const url = new URL(event.request.url);
 if(event.request.method !== 'GET' || url.origin !== self.location.origin) return;
 if(CORE.includes(url.pathname)) event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request)));
 else if(event.request.mode === 'navigate') event.respondWith(fetch(event.request).catch(() => caches.match('/static/pwa/offline.html')));
});
self.addEventListener('push', event => {
 let data={}; try { data=event.data ? event.data.json():{}; } catch(_) {}
 event.waitUntil(self.registration.showNotification(data.title||'HajjGuard',{body:data.body||'Open HajjGuard for your safety notification.',tag:data.tag||'hajjguard',data:{url:'/app/'}}));
});
self.addEventListener('notificationclick', event => {event.notification.close();event.waitUntil(clients.matchAll({type:'window',includeUncontrolled:true}).then(list=>list[0] ? list[0].focus() : clients.openWindow('/app/')));});
self.addEventListener('sync', event => {if(event.tag==='hajjguard-outbox') event.waitUntil(clients.matchAll({type:'window',includeUncontrolled:true}).then(list=>list.forEach(client=>client.postMessage({type:'flush-outbox'}))));});
