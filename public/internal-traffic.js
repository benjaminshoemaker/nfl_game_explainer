(() => {
  const key = 'nfl-analytics-internal';
  const status = document.getElementById('status');
  const render = () => {
    try {
      status.textContent = localStorage.getItem(key) === 'true'
        ? 'This browser is internal. New analytics events are excluded from the audience dashboard.'
        : 'This browser is not marked as internal.';
    } catch {
      status.textContent = 'Browser storage is unavailable. Allow site storage to save this setting.';
    }
  };
  const change = (internal) => {
    try {
      if (internal) localStorage.setItem(key, 'true');
      else localStorage.removeItem(key);
      render();
    } catch {
      status.textContent = 'Could not save the setting. Allow site storage and try again.';
    }
  };
  document.getElementById('mark-internal').addEventListener('click', () => change(true));
  document.getElementById('clear-internal').addEventListener('click', () => change(false));
  window.addEventListener('storage', render);
  render();
})();
