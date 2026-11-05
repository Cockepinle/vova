(() => {
  const key = 'pakline-theme';
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  let preference = null;
  const valid = value => value === 'light' || value === 'dark';
  try { preference = localStorage.getItem(key); } catch (_) { /* Storage can be unavailable. */ }
  if (!valid(preference)) preference = null;
  function apply() {
    const dark = (preference || (system.matches ? 'dark' : 'light')) === 'dark';
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
    document.querySelectorAll('.theme-toggle').forEach(button => {
      button.setAttribute('aria-pressed', String(dark));
      button.title = dark ? 'Включить светлую тему' : 'Включить тёмную тему';
    });
  }
  apply(); // Before rendering, to avoid a flash of the wrong theme.
  document.addEventListener('DOMContentLoaded', apply);
  document.addEventListener('click', event => {
    if (!event.target.closest('.theme-toggle')) return;
    preference = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem(key, preference); } catch (_) { /* Keep session choice. */ }
    apply();
  });
  system.addEventListener('change', () => { if (!preference) apply(); });
  window.addEventListener('storage', event => {
    if (event.key !== key && event.key !== null) return;
    preference = valid(event.newValue) ? event.newValue : null;
    apply();
  });
})();
