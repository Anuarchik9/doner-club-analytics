(() => {
  const root = document.querySelector('.presets');
  if (!root) return;

  const monthNames = [
    'Январь','Февраль','Март','Апрель','Май','Июнь',
    'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'
  ];

  function isoLocal(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }

  function monthRange(offset) {
    const now = new Date();
    const start = new Date(now.getFullYear(), now.getMonth() - offset, 1);
    const end = offset === 0
      ? new Date(now.getFullYear(), now.getMonth(), now.getDate())
      : new Date(now.getFullYear(), now.getMonth() - offset + 1, 0);
    return { from: isoLocal(start), to: isoLocal(end), label: monthNames[start.getMonth()] };
  }

  const currentMonth = monthRange(0);
  const months = [monthRange(1), monthRange(2), monthRange(3)];

  root.innerHTML = `
    <button class="preset" data-preset="current-month">Текущий месяц</button>
    <button class="preset" data-preset="yesterday" data-d="1">Вчера</button>
    <button class="preset" data-preset="day-before" data-d="2">Позавчера</button>
    ${months.map((m, i) => `<button class="preset" data-preset="month" data-month-index="${i}">${m.label}</button>`).join('')}
  `;

  function setDates(from, to, button) {
    const fromInput = document.getElementById('from');
    const toInput = document.getElementById('to');
    if (!fromInput || !toInput) return;
    fromInput.value = from;
    toInput.value = to;
    root.querySelectorAll('.preset').forEach(b => b.classList.remove('active'));
    if (button) button.classList.add('active');
  }

  root.querySelectorAll('.preset').forEach(button => {
    button.addEventListener('click', () => {
      const type = button.dataset.preset;
      const now = new Date();
      if (type === 'current-month') {
        setDates(currentMonth.from, currentMonth.to, button);
        return;
      }
      if (type === 'yesterday') {
        const d = new Date(now);
        d.setDate(d.getDate() - 1);
        const value = isoLocal(d);
        setDates(value, value, button);
        return;
      }
      if (type === 'day-before') {
        const d = new Date(now);
        d.setDate(d.getDate() - 2);
        const value = isoLocal(d);
        setDates(value, value, button);
        return;
      }
      if (type === 'month') {
        const m = months[Number(button.dataset.monthIndex) || 0];
        setDates(m.from, m.to, button);
      }
    });
  });

  const fromInput = document.getElementById('from');
  const toInput = document.getElementById('to');

  function clearPresetActive() {
    root.querySelectorAll('.preset').forEach(b => b.classList.remove('active'));
  }

  if (fromInput) {
    fromInput.addEventListener('input', clearPresetActive);
    fromInput.addEventListener('change', () => {
      clearPresetActive();
      if (!toInput || !fromInput.value) return;
      toInput.min = fromInput.value;
      if (!toInput.value || toInput.value < fromInput.value) toInput.value = fromInput.value;

      // After choosing the first date, immediately move the user to the end date.
      // showPicker works in supported mobile/desktop browsers; focus/click are safe fallbacks.
      setTimeout(() => {
        try {
          toInput.focus({ preventScroll: true });
          if (typeof toInput.showPicker === 'function') toInput.showPicker();
          else toInput.click();
        } catch (_) {
          try { toInput.focus(); } catch (_) {}
        }
      }, 80);
    });
  }

  if (toInput) {
    toInput.addEventListener('input', clearPresetActive);
    toInput.addEventListener('change', clearPresetActive);
  }
})();
