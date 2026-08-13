(function(){
  let deferredPrompt=null;
  function isStandalone(){return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone;}
  function ensureButton(){
    if(isStandalone())return null;
    let b=document.getElementById('pwa-install-button');
    if(!b){b=document.createElement('button');b.id='pwa-install-button';b.className='pwa-install-button hidden';b.type='button';b.textContent='Install Investify app';document.body.appendChild(b);}return b;
  }
  if('serviceWorker' in navigator){window.addEventListener('load',()=>navigator.serviceWorker.register('/static/service-worker.js').catch(()=>{}));}
  window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();deferredPrompt=e;const b=ensureButton();if(!b)return;b.classList.remove('hidden');b.onclick=async()=>{b.classList.add('hidden');if(!deferredPrompt)return;deferredPrompt.prompt();await deferredPrompt.userChoice.catch(()=>{});deferredPrompt=null;};});
  window.addEventListener('appinstalled',()=>{const b=document.getElementById('pwa-install-button');if(b)b.classList.add('hidden');deferredPrompt=null;});
})();
