(() => {
  if (window.__dcRevisions) return;
  window.__dcRevisions = true;

  const style = document.createElement('style');
  style.textContent = `
    .revision-shell{display:grid;gap:13px}
    .revision-cards{display:grid;grid-template-columns:repeat(4,1fr);gap:13px}
    .revision-card{padding:18px;border:1px solid var(--line);border-radius:17px;background:#0d0d0d;min-width:0}
    .revision-card small{display:block;color:var(--muted);font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.07em}
    .revision-card strong{display:block;margin-top:10px;font-size:22px;line-height:1.12;overflow-wrap:anywhere}
    .revision-card span{display:block;margin-top:7px;color:var(--muted);font-size:10px;line-height:1.45}
    .revision-grid{display:grid;grid-template-columns:1.15fr .85fr;gap:13px}
    .revision-list{display:grid;gap:8px;margin-top:15px}
    .revision-row{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center;padding:12px 13px;border:1px solid #282828;border-radius:13px;background:#0b0b0b}
    .revision-row b{font-size:12px}.revision-row span{display:block;color:var(--muted);font-size:10px;margin-top:4px}
    .revision-status{padding:13px 14px;border-radius:13px;border:1px solid #55402c;background:#1c150f;color:#e8c59e;font-size:11px;line-height:1.55;margin-top:13px}
    .revision-status.ok{border-color:#2c523d;background:#101d16;color:#a9dfbd}
    .revision-roadmap{display:grid;gap:9px;margin-top:15px}
    .revision-roadmap div{padding:11px 12px;border:1px solid #292929;border-radius:12px;background:#0b0b0b;color:#bbb;font-size:11px}
    .revision-roadmap b{color:#fff}
    @media(max-width:1000px){.revision-cards{grid-template-columns:1fr 1fr}.revision-grid{grid-template-columns:1fr}}
    @media(max-width:600px){.revision-cards{grid-template-columns:1fr}.revision-row{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);

  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function findSection(title){
    for (const h of document.querySelectorAll('.section h2')) {
      if ((h.textContent || '').trim() === title) return h.closest('.section');
    }
    return null;
  }

  const anchor = findSection('Все позиции');
  if (!anchor || document.getElementById('revisionBlock')) return;

  const head = document.createElement('div');
  head.className = 'section';
  head.id = 'revisionHead';
  head.innerHTML = '<h2>Ревизии</h2><span class="source-chip">iikoServer · склад</span>';

  const block = document.createElement('section');
  block.className = 'revision-shell';
  block.id = 'revisionBlock';
  block.innerHTML = `
    <div class="panel">
      <div style="display:flex;justify-content:space-between;gap:14px;align-items:flex-start;flex-wrap:wrap">
        <div><h3>Еженедельная ревизия</h3><div class="muted">Фактический остаток против учётного остатка iiko</div></div>
        <div class="muted" id="revisionPeriod">Ищем источник документов…</div>
      </div>
      <div class="revision-cards" style="margin-top:17px">
        <div class="revision-card"><small>Последняя ревизия</small><strong id="revisionLast">—</strong><span>Дата последнего найденного документа</span></div>
        <div class="revision-card"><small>Документов найдено</small><strong id="revisionCount">—</strong><span>За последние 8 недель</span></div>
        <div class="revision-card"><small>Источник</small><strong id="revisionSource">—</strong><span>Определяем автоматически по вашей версии iiko</span></div>
        <div class="revision-card"><small>Подключение</small><strong id="revisionConnection">…</strong><span>Проверяем складской слой</span></div>
      </div>
      <div id="revisionStatus" class="revision-status">Сейчас дашборд автоматически ищет, каким типом документа ваша версия iiko хранит инвентаризации. Никакие данные не изменяются — выполняется только чтение.</div>
    </div>
    <div class="revision-grid">
      <div class="panel">
        <h3>Последние ревизии</h3>
        <div class="muted">После определения источника здесь появятся дата, статус и ответственный сотрудник.</div>
        <div class="revision-list" id="revisionDocuments"><div class="muted">Получаем данные из iiko…</div></div>
      </div>
      <div class="panel">
        <h3>Что будет считаться автоматически</h3>
        <div class="muted">Следующий слой после определения полей документа.</div>
        <div class="revision-roadmap">
          <div><b>Недостача:</b> учётный остаток − фактический, в количестве и ₸.</div>
          <div><b>Излишки:</b> позиции, которых по факту оказалось больше учёта.</div>
          <div><b>Итог ревизии:</b> чистое отклонение и % от стоимости склада.</div>
          <div><b>Повторяемость:</b> товары, уходящие в минус несколько недель подряд.</div>
          <div><b>Динамика:</b> текущая ревизия против прошлой и накопленный итог месяца.</div>
        </div>
      </div>
    </div>`;

  anchor.insertAdjacentElement('beforebegin', block);
  block.insertAdjacentElement('beforebegin', head);

  function shortDate(value){
    if (!value) return '—';
    const m = String(value).match(/(\d{4})[-.](\d{2})[-.](\d{2})/);
    if (m) return `${m[3]}.${m[2]}.${m[1]}`;
    return String(value).slice(0, 16);
  }

  function render(j){
    const source = j?.source;
    const docs = source?.documents || [];
    document.getElementById('revisionPeriod').textContent = j?.period ? `${shortDate(j.period.from)} — ${shortDate(j.period.to)}` : 'Последние 8 недель';
    document.getElementById('revisionCount').textContent = source ? String(source.recordCount ?? docs.length ?? 0) : '0';
    document.getElementById('revisionSource').textContent = source ? source.name : 'Поиск';

    const dates = docs.map(x => x?.date).filter(Boolean).sort();
    document.getElementById('revisionLast').textContent = dates.length ? shortDate(dates[dates.length - 1]) : '—';

    const status = document.getElementById('revisionStatus');
    const connection = document.getElementById('revisionConnection');
    if (j?.status === 'source_found') {
      connection.textContent = 'Источник найден';
      status.className = 'revision-status ok';
      status.textContent = 'iikoServer подтвердил источник документов ревизии. Следующий этап — сопоставить фактическое количество, учётное количество и стоимость расхождения, после чего блок начнёт считать недостачи и излишки в ₸.';
    } else if (j?.status === 'candidate_found') {
      connection.textContent = 'Есть кандидат';
      status.className = 'revision-status';
      status.textContent = 'В iiko найдены признаки инвентаризации, но точный тип документа пока не подтверждён. Диагностика уже сохранена в ответе сервера — на следующем шаге привяжем найденный тип к расчётам.';
    } else {
      connection.textContent = 'Ищем источник';
      status.className = 'revision-status';
      status.textContent = 'Доступ к iikoServer работает, но стандартный тип документа ревизии этой версии iiko пока не найден. Сам блок уже подключён; понадобится определить конкретный складской документ вашей конфигурации.';
    }

    const root = document.getElementById('revisionDocuments');
    if (!docs.length) {
      root.innerHTML = '<div class="muted">Документы ревизии пока не распознаны автоматически.</div>';
      return;
    }
    root.innerHTML = docs.slice(0, 8).map((d, i) => {
      const title = d.number || d.name || `Ревизия ${i + 1}`;
      const meta = [shortDate(d.date), d.status, d.responsible, d.store].filter(x => x && x !== '—').join(' · ');
      return `<div class="revision-row"><div><b>${esc(title)}</b><span>${esc(meta || 'Документ iiko')}</span></div><div class="muted">${esc(d.id ? String(d.id).slice(0, 8) : '')}</div></div>`;
    }).join('');
  }

  async function load(){
    const point = document.getElementById('point')?.value || 'Arai';
    try {
      const r = await fetch(`/revision-discovery?point=${encodeURIComponent(point)}&weeks=8`, {headers:{Accept:'application/json'}});
      const text = await r.text();
      let j = null;
      try { j = text ? JSON.parse(text) : null; } catch (_) {}
      if (!r.ok || !j?.success) throw new Error(j?.message || `HTTP ${r.status}`);
      render(j);
    } catch (e) {
      document.getElementById('revisionConnection').textContent = 'Ошибка';
      const status = document.getElementById('revisionStatus');
      status.className = 'revision-status';
      status.textContent = `Не удалось проверить ревизии: ${e.message}`;
      document.getElementById('revisionDocuments').innerHTML = '<div class="muted">Проверка источника не завершена.</div>';
    }
  }

  document.getElementById('go')?.addEventListener('click', () => setTimeout(load, 500));
  document.getElementById('point')?.addEventListener('change', () => setTimeout(load, 150));
  setTimeout(load, 1400);
})();
