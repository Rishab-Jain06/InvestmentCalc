const CACHE_NAME='investify-v53-shell';
const SHELL=['/','/portfolio','/static/css/site.css','/static/manifest.webmanifest','/static/img/favicon.png?v=3'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE_NAME).then(cache=>cache.addAll(SHELL).catch(()=>{})));self.skipWaiting();});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE_NAME).map(k=>caches.delete(k)))));self.clients.claim();});
self.addEventListener('fetch',event=>{const req=event.request;if(req.method!=='GET')return;const url=new URL(req.url);if(url.pathname.startsWith('/api/'))return;event.respondWith(fetch(req).then(res=>{const copy=res.clone();caches.open(CACHE_NAME).then(cache=>cache.put(req,copy)).catch(()=>{});return res;}).catch(()=>caches.match(req).then(cached=>cached||caches.match('/'))));});
