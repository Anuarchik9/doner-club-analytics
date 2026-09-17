(() => {
  if (window.__dcPointArchivePolish) return;
  window.__dcPointArchivePolish = true;
  if (!location.pathname.endsWith('/dashboard-v2.html')) return;

  const select = document.getElementById('point');
  if (!select) return;

  const hiddenPoint = text => {
    const low = String(text || '').trim().toLowerCase();
    return low.includes('улы дала') || low.includes('uly dala') || low.includes('цех основной');
  };

  const archivePoint = text => {
    const low = String(text || '').trim().toLowerCase();
    return low.includes('манас') || low.includes('сыганак');
  };

  function pruneNative() {
    let changed = false;
    Array.from(select.options).forEach(option => {
      if (option.dataset.dcMultiSynthetic) return;
      if (hiddenPoint(option.textContent)) {
        option.remove();
        changed = true;
      }
    });
    if (changed) {
      select.dispatchEvent(new Event('change', {bubbles:true}));
    }
  }

  function polishPanel() {
    document.querySelectorAll('.dc-point-option').forEach(button => {
      const text = button.querySelector('.dc-point-option-text');
      if (!text) return;
      const label = text.textContent.trim();
      if (hiddenPoint(label)) {
        button.remove();
        return;
      }
      if (archivePoint(label) && !button.querySelector('.dc-point-archive-badge')) {
        const badge = document.createElement('span');
        badge.className = 'dc-point-badge dc-point-archive-badge';
        badge.textContent = 'на реконструкции';
        button.appendChild(badge);
      }
    });
  }

  pruneNative();
  polishPanel();

  const observer = new MutationObserver(() => {
    pruneNative();
    polishPanel();
  });
  observer.observe(document.body, {childList:true, subtree:true});

  setTimeout(pruneNative, 120);
  setTimeout(polishPanel, 180);
  setTimeout(pruneNative, 700);
  setTimeout(polishPanel, 760);
})();
