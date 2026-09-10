/* No reload handler: a new controller must never interrupt a reader. */
(() => {
  if (!('serviceWorker' in navigator) || !window.isSecureContext || location.protocol === 'file:') return;
  const root = new URL('./', location.href);
  const release = document.querySelector('meta[name="essaylab-release"]').content;
  let registration, lastCheck = 0, starting;
  function announce() {
    navigator.serviceWorker.controller?.postMessage({type: 'CLIENT_RELEASE', release});
  }
  navigator.serviceWorker.addEventListener('controllerchange', announce);
  navigator.serviceWorker.addEventListener('message', event => {
    if (event.data?.type === 'REQUEST_RELEASE') announce();
    if (event.data?.type === 'OFFLINE_READY') {
      document.documentElement.dataset.offlineReady = 'true';
      window.dispatchEvent(new CustomEvent('essaylab:offline-ready'));
    }
  });
  async function check() {
    if (!navigator.onLine || document.visibilityState === 'hidden') return;
    // A failed first installation can remove the registration altogether.
    if (!registration || !await navigator.serviceWorker.getRegistration(root.href)) {
      registration = null;
      return start();
    }
    if (Date.now() - lastCheck < 60000) return;
    lastCheck = Date.now();
    try { await registration.update(); } catch { lastCheck = 0; }
    announce();
  }
  function start() {
    if (starting) return starting;
    starting = navigator.serviceWorker.register(new URL('sw.js', root), {
      scope: root.href, updateViaCache: 'none'
    }).then(reg => {
      registration = reg;
      lastCheck = Date.now();
      // Do not keep start() pending on ready: failed installations never resolve it.
      navigator.serviceWorker.ready.then(announce);
      announce();
    }).catch(error => {
      console.warn('EssayLab offline setup will retry when online.', error);
    }).finally(() => { starting = null; });
    return starting;
  }
  window.addEventListener('online', check);
  window.addEventListener('pageshow', check);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) check(); });
  setInterval(check, 30 * 60 * 1000);
  start();
})();
