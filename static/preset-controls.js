(() => {
  if (window.__dcPresetControlsV2) return;
  window.__dcPresetControlsV2 = true;

  const root = document.querySelector('.presets');
  if (!root) return;

  const monthNames = [
    'Январь','Февраль','Март','Апрель','Май','Июнь',
    'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'
  ];

  const fromInput = document.getElementById('from');
  const toInput = document.getElementById('to');
  let renderedDayKey = '';
  let suppressManualHandlers = false;

  function isoLocal(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }

  function todayKey() {
    return isoLocal(new Date());
  }

  function startOfWeek(d) {
    const date = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const day = date.getDay();
    const diff = day === 0 ? -6 : 1 - day;
    date.setDate(date.getDate() + diff);
    return date;
  }

  function weekRange(offsetWeeks = 0, now = new Date()) {
    const monday = startOfWeek(now);
    monday.setDate(monday.getDate() - offsetWeeks * 7);
    const end = new Date(monday);
    if (offsetWeeks === 0) {
      end.setFullYear(now.getFullYear(), now.getMonth(), now.getDate());
    } else {
      end.setDate(end.getDate() + 6);
    }
    return { from: isoLocal(monday), to: isoLocal(end) };
  }

  function monthRange(offset, now = new Date()) {
    const start = new Date(now.getFullYear(), now.getMonth() - offset, 1);
    const end = offset === 0
      ? new Date(now.getFullYear(), now.getMonth(), now.getDate())
      : new Date(now.getFullYear(), now.getMonth() - offset + 1, 0);
    return {
      from: isoLocal(start),
      to: isoLocal(end),
      label: monthNames[start.getMonth()],
      year: start.getFullYear()
    };
  }

  function periodsNow() {
    const now = new Date();
    return {
      now,
      currentWeek: weekRange(0, now),
      previousWeek: weekRange(1, now),
      currentMonth: monthRange(0, now),
      months: [monthRange(1, now), monthRange(2, now), monthRange(3, now)]
    };
  }

  function emitInput(input) {
    if (!input) return;
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function setDates(from, to, button) {
    if (!fromInput || !toInput) return;
    suppressManualHandlers = true;
    try {
      fromInput.value = from;
      toInput.min = from;
      toInput.value = to;
      emitInput(fromInput);
      emitInput(toInput);
    } finally {
      suppressManualHandlers = false;
    }
    root.querySelectorAll('.preset').forEach(b => b.classList.remove('active'));
    if (button) button.classList.add('active');
  }

  function presetMatches(button) {
    if (!fromInput || !toInput || !fromInput.value || !toInput.value) return false;
    const p = periodsNow();
    const type = button.dataset.preset;
    let from = '', to = '';
    if (type === 'today') {
      from = to = isoLocal(p.now);
    } else if (type === 'yesterday' || type === 'day-before') {
      const d = new Date(p.now);
      d.setDate(d.getDate() - (type === 'yesterday' ? 1 : 2));
      from = to = isoLocal(d);
    } else if (type === 'current-week') {
      ({ from, to } = p.currentWeek);
    } else if (type === 'previous-week') {
      ({ from, to } = p.previousWeek);
    } else if (type === 'current-month') {
      ({ from, to } = p.currentMonth);
    } else if (type === 'month') {
      const m = p.months[Number(button.dataset.monthIndex) || 0];
      if (m) ({ from, to } = m);
    }
    return fromInput.value === from && toInput.value === to;
  }

  function syncActive() {
    const buttons = Array.from(root.querySelectorAll('.preset'));
    const matched = buttons.find(presetMatches);
    buttons.forEach(button => button.classList.toggle('active', button === matched));
  }

  function bindPreset(button) {
    button.addEventListener('click', () => {
      const p = periodsNow();
      const type = button.dataset.preset;
      if (type === 'today') {
        const value = isoLocal(p.now);
        setDates(value, value, button);
        return;
      }
      if (type === 'yesterday' || type === 'day-before') {
        const d = new Date(p.now);
        d.setDate(d.getDate() - (type === 'yesterday' ? 1 : 2));
        const value = isoLocal(d);
        setDates(value, value, button);
        return;
      }
      if (type === 'current-week') {
        setDates(p.currentWeek.from, p.currentWeek.to, button);
        return;
      }
      if (type === 'previous-week') {
        setDates(p.previousWeek.from, p.previousWeek.to, button);
        return;
      }
      if (type === 'current-month') {
        setDates(p.currentMonth.from, p.currentMonth.to, button);
        return;
      }
      if (type === 'month') {
        const m = p.months[Number(button.dataset.monthIndex) || 0];
        if (m) setDates(m.from, m.to, button);
      }
    });
  }

  function renderPresets(force = false) {
    const key = todayKey();
    if (!force && renderedDayKey === key) return;
    renderedDayKey = key;

    const { months } = periodsNow();
    root.innerHTML = `
      <button class="preset" data-preset="today">Сегодня</button>
      <button class="preset" data-preset="yesterday">Вчера</button>
      <button class="preset" data-preset="day-before">Позавчера</button>
      <button class="preset" data-preset="current-week">Текущая неделя</button>
      <button class="preset" data-preset="previous-week">Прошлая неделя</button>
      <button class="preset" data-preset="current-month">Текущий месяц</button>
      ${months.map((m, i) => `<button class="preset" data-preset="month" data-month-index="${i}">${m.label}</button>`).join('')}
    `;
    root.querySelectorAll('.preset').forEach(bindPreset);
    syncActive();
  }

  function clearPresetActive() {
    if (suppressManualHandlers) return;
    root.querySelectorAll('.preset').forEach(b => b.classList.remove('active'));
  }

  function openCustomToPicker() {
    if (!toInput) return;
    let tries = 0;
    const attempt = () => {
      const trigger = document.querySelector('.dc-picker-trigger[data-for="to"]');
      if (trigger) {
        trigger.click();
        return;
      }
      if (++tries < 8) setTimeout(attempt, 25);
    };
    setTimeout(attempt, 40);
  }

  if (fromInput) {
    fromInput.addEventListener('input', clearPresetActive);
    fromInput.addEventListener('change', () => {
      if (suppressManualHandlers) return;
      clearPresetActive();
      if (!toInput || !fromInput.value) return;
      toInput.min = fromInput.value;
      if (!toInput.value || toInput.value < fromInput.value) {
        toInput.value = fromInput.value;
        emitInput(toInput);
      }
      // Always open the Doner Club custom picker, never the browser-native calendar.
      openCustomToPicker();
    });
  }

  if (toInput) {
    toInput.addEventListener('input', clearPresetActive);
    toInput.addEventListener('change', clearPresetActive);
  }

  renderPresets(true);

  // Every fresh page load starts on the actual current day. This deliberately
  // overrides the legacy dashboard default (which could leave yesterday selected)
  // and also marks the «Сегодня» preset active.
  const initialToday = isoLocal(new Date());
  setDates(initialToday, initialToday, root.querySelector('[data-preset="today"]'));

  // If the page remains open over midnight / the first day of a new month,
  // refresh the rolling month buttons automatically. Example: on 1 October
  // they become September, August, July; June disappears without a deploy.
  setInterval(() => renderPresets(false), 60 * 1000);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) renderPresets(false);
  });
  window.addEventListener('focus', () => renderPresets(false));
})();