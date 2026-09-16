(() => {
  if (window.__dcRevisionsUi) return;
  window.__dcRevisionsUi = true;

  const $ = id => document.getElementById(id);
  const button = $('revisionShow');
  const filters = document.querySelector('.filters');
  if (!button || !filters) return;

  const style = document.createElement('style');
  style.textContent = `
    .revision-status{display:none;margin-top:12px;padding:13px 15px;border:1px solid #3a342d;border-radius:14px;background:#14110e;color:#c8b7a8;font-size:12px;line-height:1.5}
    .revision-status.show{display:block}
    .revision-status.ok{border-color:#294739;background:#0d1712;color:#9fe4bf}
    .revision-status.warn{border-color:#5a4228;background:#1b140d;color:#efc699}
    .revision-status.err{border-color:#653232;background:#211010;color:#ffb2b2}
    .revision-status b{color:#fff}
    .go[disabled]{opacity:.65;cursor:wait}
  `;
  document.head.appendChild(style);

  const status = document.createElement('div');
  status.id = 'revisionStatus';
  status.className = 'revision-status';
  filters.insertAdjacentElement('afterend', status);

  const monthNames = ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
  const monthLabel = value => {
    const m = /^(\d{4})-(\d{2})$/.exec(String(value || ''));
    if (!m) return value || '—';
    return `${monthNames[Number(m[2]) - 1]} ${m[1]}`;
  };

  function show(kind, html) {
    status.className = `revision-status show ${kind || ''}`.trim();
    status.innerHTML = html;
  }

  async function verifyIiko() {
    const response = await fetch('/olap-departments', {headers:{Accept:'application/json'}, cache:'no-store'});
    let data = null;
    try { data = await response.json(); } catch (_) {}
    if (response.status === 401) {
      location.href = `/login?next=${encodeURIComponent(location.pathname)}`;
      return null;
    }
    if (!response.ok || !data?.success) throw new Error(data?.message || `HTTP ${response.status}`);
    return data;
  }

  button.addEventListener('click', async () => {
    const point = $('revisionPoint')?.selectedOptions?.[0]?.textContent?.trim() || 'Точка';
    const period = $('revisionPeriod')?.value;
    if (!period) {
      show('err', 'Выбери месяц ревизии.');
      return;
    }

    button.disabled = true;
    const oldText = button.textContent;
    button.textContent = 'Проверяем…';
    show('', `<b>${point} · ${monthLabel(period)}</b><br>Проверяем соединение с iikoServer…`);

    try {
      const result = await verifyIiko();
      if (!result) return;
      show('warn', `<b>${point} · ${monthLabel(period)}</b><br>iikoServer доступен. Кнопка работает. Сейчас для раздела «Ревизии» ещё подключаем именно документы инвентаризации — поэтому суммы пока не подставляются.`);
    } catch (error) {
      show('err', `<b>Не удалось проверить iikoServer.</b><br>${String(error?.message || error)}`);
    } finally {
      button.disabled = false;
      button.textContent = oldText;
    }
  });
})();
