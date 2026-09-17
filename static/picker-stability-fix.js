(() => {
  if (window.__dcPickerStabilityFix) return;
  window.__dcPickerStabilityFix = true;

  const KNOWN_IDS = new Set(['from', 'to', 'dcSalesMonth']);
  let repairing = false;

  const style = document.createElement('style');
  style.textContent = `
    /* Never let the browser's native date/month control flash through after the
       Doner Club custom picker has taken ownership of the field. */
    input[type="date"][data-dc-picker-enhanced="1"],
    input[type="month"][data-dc-picker-enhanced="1"],
    input[type="date"].dc-native-picker,
    input[type="month"].dc-native-picker {
      position:absolute!important;
      width:1px!important;
      height:1px!important;
      opacity:0!important;
      pointer-events:none!important;
      overflow:hidden!important;
      clip:rect(0 0 0 0)!important;
    }
  `;
  document.head.appendChild(style);

  const isPickerInput = input => {
    if (!(input instanceof HTMLInputElement)) return false;
    if (!['date', 'month'].includes(input.type)) return false;
    return !!input.closest('.field') || KNOWN_IDS.has(input.id);
  };

  const triggerFor = input => {
    if (!input?.id) return null;
    try {
      return document.querySelector(`.dc-picker-trigger[data-for="${CSS.escape(input.id)}"]`);
    } catch (_) {
      return document.querySelector(`.dc-picker-trigger[data-for="${input.id}"]`);
    }
  };

  function forceWidePickerBoot(input) {
    if (!input || !input.isConnected) return;

    // The main picker enhancer uses this flag. If a DOM redraw preserved the
    // flag but removed its trigger, reset it so the enhancer can rebuild UI.
    delete input.dataset.dcPickerEnhanced;
    input.classList.remove('dc-native-picker');

    // wide-period-click watches added DOM nodes. A harmless marker forces its
    // boot() to run again without reloading the page.
    const marker = document.createElement('i');
    marker.hidden = true;
    marker.dataset.dcPickerRepair = '1';
    (input.closest('.field') || input.parentElement || document.body).appendChild(marker);
    queueMicrotask(() => marker.remove());
  }

  function dedupeTriggers(input) {
    if (!input?.id) return;
    let triggers = [];
    try {
      triggers = Array.from(document.querySelectorAll(`.dc-picker-trigger[data-for="${CSS.escape(input.id)}"]`));
    } catch (_) {
      triggers = Array.from(document.querySelectorAll(`.dc-picker-trigger[data-for="${input.id}"]`));
    }
    if (triggers.length <= 1) return;
    const keep = triggers.find(node => node.isConnected) || triggers[0];
    triggers.forEach(node => { if (node !== keep) node.remove(); });
  }

  function repairInput(input) {
    if (!isPickerInput(input)) return;
    dedupeTriggers(input);
    const trigger = triggerFor(input);
    if (trigger?.isConnected) {
      input.classList.add('dc-native-picker');
      input.dataset.dcPickerEnhanced = '1';
      return;
    }
    forceWidePickerBoot(input);
  }

  function repairAll() {
    if (repairing) return;
    repairing = true;
    try {
      document.querySelectorAll('input[type="date"], input[type="month"]').forEach(repairInput);
    } finally {
      repairing = false;
    }
  }

  function openCustomFor(input) {
    repairInput(input);
    let attempts = 0;
    const open = () => {
      const trigger = triggerFor(input);
      if (trigger?.isConnected) {
        trigger.click();
        return;
      }
      if (++attempts < 8) {
        forceWidePickerBoot(input);
        setTimeout(open, 20);
      }
    };
    queueMicrotask(open);
  }

  // Hard guard: native browser calendars must never open for fields owned by
  // the custom picker, even during a redraw/race after the first date changes.
  ['pointerdown', 'mousedown', 'click'].forEach(type => {
    document.addEventListener(type, event => {
      const input = event.target instanceof HTMLInputElement ? event.target : null;
      if (!isPickerInput(input)) return;
      const customOwned = input.dataset.dcPickerEnhanced === '1' || input.classList.contains('dc-native-picker') || KNOWN_IDS.has(input.id);
      if (!customOwned) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      if (type === 'click') openCustomFor(input);
    }, true);
  });

  // Redraws caused by presets/mode/date changes can replace just one field.
  // Repair immediately and again on the next frames so both FROM and TO always
  // keep the same Doner Club picker.
  const observer = new MutationObserver(() => {
    repairAll();
    requestAnimationFrame(repairAll);
    setTimeout(repairAll, 30);
  });
  observer.observe(document.documentElement, {childList:true, subtree:true});

  document.addEventListener('change', event => {
    if (isPickerInput(event.target)) {
      setTimeout(repairAll, 0);
      setTimeout(repairAll, 40);
      setTimeout(repairAll, 140);
    }
  }, true);

  repairAll();
  requestAnimationFrame(repairAll);
  setTimeout(repairAll, 50);
  setTimeout(repairAll, 180);
  setTimeout(repairAll, 600);
})();
