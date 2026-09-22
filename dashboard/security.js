// One shared unlock dialog for simultaneous API requests. The PIN is never stored.
(() => {
  const nativeFetch = window.fetch.bind(window);
  let unlocking = null;
  function unlock() {
    if (unlocking) return unlocking;
    unlocking = new Promise((resolve, reject) => {
      const dialog = document.createElement('dialog');
      dialog.setAttribute('aria-labelledby', 'unlock-title');
      dialog.style.cssText = 'background:#111827;color:#f1f5f9;border:1px solid #64748b;border-radius:12px;padding:28px;max-width:360px;z-index:99999';
      dialog.innerHTML = '<form><h2 id="unlock-title">Unlock dashboard</h2><p>Enter your saved dashboard PIN.</p><label>PIN <input name="pin" type="password" inputmode="numeric" autocomplete="off" required autofocus></label><p role="alert"></p><button type="submit">Unlock</button><button type="button">Cancel</button></form>';
      document.body.appendChild(dialog);
      const finish = error => { dialog.close(); dialog.remove(); error ? reject(error) : resolve(); };
      dialog.querySelector('button[type=button]').onclick = () => finish(new Error('Dashboard locked'));
      dialog.addEventListener('cancel', event => { event.preventDefault(); finish(new Error('Dashboard locked')); });
      dialog.querySelector('form').onsubmit = async event => {
        event.preventDefault();
        const button = dialog.querySelector('button[type=submit]');
        button.disabled = true;
        try {
          const response = await nativeFetch('/api/unlock', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pin:dialog.querySelector('input').value})});
          const data = await response.json();
          if (!response.ok) throw new Error(data.error || 'Unlock failed');
          finish();
        } catch(error) { dialog.querySelector('[role=alert]').textContent = error.message; }
        finally { button.disabled = false; }
      };
      dialog.showModal();
    }).finally(() => { unlocking = null; });
    return unlocking;
  }
  window.logoutDashboard = async () => {
    await nativeFetch('/api/logout', {method: 'POST'});
    window.location.href = '/login';
  };
  window.fetch = async (input, options) => {
    let response = await nativeFetch(input, options);
    const url = new URL(typeof input === 'string' ? input : input.url, location.href);
    if (url.origin === location.origin && url.pathname.startsWith('/api/') && response.status === 401) {
      const data = await response.clone().json().catch(() => ({}));
      if (data.code === 'PIN_REQUIRED') {
        await unlock();
        response = await nativeFetch(input, options);
      }
    }
    return response;
  };
})();
