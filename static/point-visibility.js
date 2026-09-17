(() => {
  if (window.__dcPointVisibility) return;
  window.__dcPointVisibility = true;
  if (!location.pathname.endsWith('/dashboard-v2.html')) return;

  const select = document.getElementById('point');
  if (!select) return;

  const HIDDEN_TOKENS = [
    'цех основной',
    'основной цех',
    'улы дала',
    'ұлы дала',
  ];

  const normalize = value => String(value || '')
    .trim()
    .toLowerCase()
    .replace(/ё/g, 'е')
    .replace(/\s+/g, ' ');

  const shouldHide = option => {
    const haystack = `${normalize(option?.textContent)} ${normalize(option?.value)}`;
    return HIDDEN_TOKENS.some(token => haystack.includes(token));
  };

  let cleaning = false;

  function cleanup() {
    if (cleaning) return;
    cleaning = true;
    try {
      let selectedWasRemoved = false;
      Array.from(select.options).forEach(option => {
        if (!shouldHide(option)) return;
        if (option.selected) selectedWasRemoved = true;
        option.remove();
      });

      if (selectedWasRemoved || !select.value) {
        const fallback = Array.from(select.options).find(option => {
          const text = normalize(option.textContent);
          const value = normalize(option.value);
          return text.includes('арай') || value === 'arai';
        }) || select.options[0];

        if (fallback) {
          select.value = fallback.value;
          select.dispatchEvent(new Event('input', { bubbles: true }));
          select.dispatchEvent(new Event('change', { bubbles: true }));
        }
      }

      document.querySelectorAll('.dc-point-panel .dc-point-option').forEach(button => {
        const text = normalize(button.textContent);
        const value = normalize(button.dataset.value);
        if (HIDDEN_TOKENS.some(token => `${text} ${value}`.includes(token))) {
          button.remove();
        }
      });
    } finally {
      cleaning = false;
    }
  }

  cleanup();

  new MutationObserver(() => cleanup()).observe(select, {
    childList: true,
    subtree: true,
    characterData: true,
  });

  new MutationObserver(() => cleanup()).observe(document.body, {
    childList: true,
    subtree: true,
  });

  window.addEventListener('dc:points-changed', cleanup);
  setTimeout(cleanup, 50);
  setTimeout(cleanup, 250);
  setTimeout(cleanup, 1000);
})();
