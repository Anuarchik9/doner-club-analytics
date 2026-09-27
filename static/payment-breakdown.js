(() => {
  'use strict';

  const byId = id => document.getElementById(id);
  const moneyFmt = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 });
  const pctFmt = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 });

  const money = value => `${moneyFmt.format(Number(value || 0))} ₸`;
  const pct = value => `${pctFmt.format(Number(value || 0))}%`;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));

  function periodText(a, b) {
    const fmt = value => {
      const parts = String(value || '').split('-');
      return parts.length === 3 ? `${parts[2]}.${parts[1]}.${parts[0]}` : String(value || '');
    };
    return a === b ? fmt(a) : `${fmt(a)} — ${fmt(b)}`;
  }

  function ensureStyle() {
    if (byId('dc-payment-breakdown-style')) return;
    const style = document.createElement('style');
    style.id = 'dc-payment-breakdown-style';
    style.textContent = `
      .dc-payment-head{display:flex;align-items:flex-end;justify-content:space-between;gap:14px;margin:20px 0 10px}
      .dc-payment-head h2{margin:0;font-size:20px}
      .dc-payment-head span{font-size:10px;color:var(--muted,#777)}
      .dc-payment-panel{border:1px solid var(--line,#2b2b2b);border-radius:20px;background:linear-gradient(160deg,#151515,#101010);padding:8px 18px}
      .dc-payment-row{display:grid;grid-template-columns:minmax(180px,1fr) auto 86px;align-items:center;gap:18px;min-height:54px;border-bottom:1px solid rgba(255,255,255,.07)}
      .dc-payment-row:last-child{border-bottom:0}
      .dc-payment-name{font-size:13px;font-weight:850;color:#f1f1f1}
      .dc-payment-amount{font-size:15px;font-weight:950;color:#fff;white-space:nowrap}
      .dc-payment-share{text-align:right;font-size:13px;font-weight:900;color:#ff7a45;white-space:nowrap}
      .dc-payment-empty{padding:24px 4px;color:var(--muted,#777);font-size:12px}
      .dc-payment-note{margin-top:8px;color:#777;font-size:10px;line-height:1.45}

      .dc-payment-chart-panel{border:1px solid var(--line,#2b2b2b);border-radius:20px;background:linear-gradient(160deg,#151515,#101010);padding:20px}
      .dc-payment-chart-title{display:flex;align-items:flex-end;justify-content:space-between;gap:14px;margin-bottom:18px}
      .dc-payment-chart-title h3{margin:0;font-size:16px}
      .dc-payment-chart-title span{font-size:10px;color:var(--muted,#777)}
      .dc-payment-chart{display:grid;gap:13px}
      .dc-payment-bar-row{display:grid;grid-template-columns:155px minmax(120px,1fr) 185px;gap:13px;align-items:center}
      .dc-payment-bar-label{font-size:11px;font-weight:800;color:#dedede;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .dc-payment-bar-track{height:14px;border-radius:999px;background:#222;overflow:hidden;border:1px solid rgba(255,255,255,.05)}
      .dc-payment-bar-fill{height:100%;min-width:2px;border-radius:999px;background:linear-gradient(90deg,#ff5a1f,#ff7d48)}
      .dc-payment-bar-value{text-align:right;font-size:11px;color:#bdbdbd;white-space:nowrap}
      .dc-payment-bar-value strong{color:#fff;font-size:12px}
      .dc-payment-bar-row{position:relative}
      .dc-payment-chart-tooltip{position:fixed;z-index:9999;pointer-events:none;display:none;min-width:132px;padding:9px 11px;border:1px solid rgba(255,255,255,.12);border-radius:10px;background:#0c0c0c;box-shadow:0 10px 28px rgba(0,0,0,.35);font-size:10px;color:#aaa;transform:translate(12px,-50%)}
      .dc-payment-chart-tooltip b{display:block;margin-top:3px;font-size:15px;color:#ff7846}
      .dc-payment-chart-foot{margin-top:16px;padding-top:12px;border-top:1px solid rgba(255,255,255,.07);display:flex;justify-content:space-between;gap:12px;color:#777;font-size:10px}
      @media(max-width:760px){
        .dc-payment-head,.dc-payment-chart-title{align-items:flex-start;flex-direction:column}
        .dc-payment-row{grid-template-columns:1fr auto;gap:5px 12px;padding:10px 0}
        .dc-payment-name{grid-column:1}
        .dc-payment-amount{grid-column:1}
        .dc-payment-share{grid-column:2;grid-row:1/3;align-self:center}
        .dc-payment-bar-row{grid-template-columns:1fr 92px;gap:7px 10px}
        .dc-payment-bar-label{grid-column:1/3}
        .dc-payment-bar-track{grid-column:1}
        .dc-payment-bar-value{grid-column:2}
        .dc-payment-chart-foot{flex-direction:column}
      }
    `;
    document.head.appendChild(style);
  }

  function ensureDetailBlock() {
    ensureStyle();
    let wrap = byId('paymentBreakdownWrap');
    if (wrap) return wrap;
    const mix = byId('channelMixWrap');
    if (!mix) return null;

    wrap = document.createElement('section');
    wrap.id = 'paymentBreakdownWrap';
    wrap.innerHTML = `
      <div class="dc-payment-head">
        <h2>Детализация по типам оплаты</h2>
        <span id="paymentBreakdownPeriod">По выбранному периоду</span>
      </div>
      <div class="dc-payment-panel" id="paymentBreakdownRows">
        <div class="dc-payment-empty">Данные появятся после загрузки отчёта.</div>
      </div>
      <div class="dc-payment-note" id="paymentBreakdownNote">Доля каждого типа считается от общей выручки выбранного периода.</div>
    `;
    mix.insertAdjacentElement('afterend', wrap);
    return wrap;
  }

  function ensureChartBlock() {
    ensureStyle();
    let head = byId('paymentChartHead');
    let panel = byId('paymentChartPanel');
    if (head && panel) return { head, panel };

    const trend = byId('staticMonthTrend');
    if (!trend) return null;

    head = document.createElement('div');
    head.className = 'section';
    head.id = 'paymentChartHead';
    head.innerHTML = '<h2>Структура выручки по типам оплаты</h2><span class="source-chip">iikoServer OLAP</span>';

    panel = document.createElement('section');
    panel.className = 'dc-payment-chart-panel';
    panel.id = 'paymentChartPanel';
    panel.innerHTML = `
      <div class="dc-payment-chart-title">
        <div><h3>Доля каждого типа оплаты</h3><span id="paymentChartPeriod">По выбранному периоду</span></div>
        <span id="paymentChartTotal">Общая выручка: —</span>
      </div>
      <div class="dc-payment-chart" id="paymentChartRows">
        <div class="dc-payment-empty">Данные появятся после загрузки отчёта.</div>
      </div>
      <div class="dc-payment-chart-tooltip" id="paymentChartTooltip"></div>
      <div class="dc-payment-chart-foot"><span>Наведите курсор на строку, чтобы увидеть процент от общей выручки.</span><span id="paymentChartCoverage"></span></div>
    `;

    trend.insertAdjacentElement('afterend', head);
    head.insertAdjacentElement('afterend', panel);
    return { head, panel };
  }

  function normalizedDetails(mix) {
    const rows = Array.isArray(mix?.paymentDetails) ? mix.paymentDetails.slice() : [];
    return rows
      .filter(item => Number(item?.revenue || 0) > 0)
      .sort((a, b) => Number(b.revenue || 0) - Number(a.revenue || 0));
  }

  function render(payload) {
    const mix = payload?.mix;
    const a = payload?.from || payload?.a || '';
    const b = payload?.to || payload?.b || a;
    const detailWrap = ensureDetailBlock();
    const chartShell = ensureChartBlock();

    if (!detailWrap) return;
    const detailRoot = byId('paymentBreakdownRows');
    const period = periodText(a, b);

    if (byId('paymentBreakdownPeriod')) byId('paymentBreakdownPeriod').textContent = period || 'По выбранному периоду';

    if (!mix || mix._error) {
      detailRoot.innerHTML = '<div class="dc-payment-empty">Не удалось загрузить детализацию по оплатам.</div>';
      if (chartShell && byId('paymentChartRows')) byId('paymentChartRows').innerHTML = '<div class="dc-payment-empty">Диаграмма временно недоступна.</div>';
      return;
    }

    const rows = normalizedDetails(mix);
    const total = Number(mix.totalRevenue || 0);
    const detailed = rows.reduce((sum, item) => sum + Number(item.revenue || 0), 0);

    detailRoot.innerHTML = rows.length ? rows.map(item => `
      <div class="dc-payment-row">
        <div class="dc-payment-name">${esc(item.label || item.key || 'Оплата')}</div>
        <div class="dc-payment-amount">${money(item.revenue)}</div>
        <div class="dc-payment-share">${pct(item.share)}</div>
      </div>
    `).join('') : '<div class="dc-payment-empty">За выбранный период оплат по известным типам не найдено.</div>';

    const other = Number(mix.other?.revenue || 0);
    const team = Number(mix.teamMeal?.revenue || 0);
    const excluded = Number(mix.excluded?.revenue || 0);
    let note = 'Доля каждого типа рассчитана от общей денежной выручки по OLAP.';
    if (team > 0) note += ` Питание команды входит в общий объём: ${money(team)}.`;
    if (other > 0) note += ` Не распределено по типу оплаты: ${money(other)}.`;
    if (excluded > 0) note += ` Баллы/бонусы не включены в денежную базу: ${money(excluded)}.`;
    byId('paymentBreakdownNote').textContent = note;

    if (!chartShell) {
      let attempts = 0;
      const timer = setInterval(() => {
        attempts += 1;
        const ready = ensureChartBlock();
        if (ready || attempts > 30) {
          clearInterval(timer);
          if (ready) render(payload);
        }
      }, 200);
      return;
    }

    if (byId('paymentChartPeriod')) byId('paymentChartPeriod').textContent = period || 'По выбранному периоду';
    if (byId('paymentChartTotal')) byId('paymentChartTotal').textContent = `Общая выручка: ${money(total)}`;

    const chartRoot = byId('paymentChartRows');
    chartRoot.innerHTML = rows.length ? rows.map(item => {
      const share = Math.max(0, Math.min(100, Number(item.share || 0)));
      return `
        <div class="dc-payment-bar-row" data-payment-label="${esc(item.label)}" data-payment-share="${share}" data-payment-revenue="${Number(item.revenue || 0)}">
          <div class="dc-payment-bar-label">${esc(item.label)}</div>
          <div class="dc-payment-bar-track"><div class="dc-payment-bar-fill" style="width:${share}%"></div></div>
          <div class="dc-payment-bar-value"><strong>${money(item.revenue)}</strong></div>
        </div>
      `;
    }).join('') : '<div class="dc-payment-empty">Нет данных для диаграммы.</div>';

    const tooltip = byId('paymentChartTooltip');
    const hideTooltip = () => { if (tooltip) tooltip.style.display = 'none'; };
    chartRoot.querySelectorAll('.dc-payment-bar-row').forEach(row => {
      const showTooltip = event => {
        if (!tooltip) return;
        const share = Number(row.dataset.paymentShare || 0);
        tooltip.innerHTML = `<span>Доля от общей выручки</span><b>${pct(share)}</b>`;
        const x = event.clientX || row.getBoundingClientRect().right;
        const y = event.clientY || (row.getBoundingClientRect().top + row.getBoundingClientRect().height / 2);
        tooltip.style.left = `${Math.min(window.innerWidth - 165, Math.max(8, x))}px`;
        tooltip.style.top = `${Math.min(window.innerHeight - 45, Math.max(45, y))}px`;
        tooltip.style.display = 'block';
      };
      row.addEventListener('pointerenter', showTooltip);
      row.addEventListener('pointermove', showTooltip);
      row.addEventListener('pointerleave', hideTooltip);
      row.addEventListener('pointerdown', showTooltip);
    });

    if (byId('paymentChartCoverage')) {
      const coverage = total > 0 ? detailed / total * 100 : 0;
      byId('paymentChartCoverage').textContent = `Детализировано: ${pct(coverage)} общей выручки`;
    }
  }

  window.addEventListener('dc:sales-mix', event => render(event.detail || {}));

  function boot() {
    ensureDetailBlock();
    ensureChartBlock();
    if (window.__dcSalesMixPayload) render(window.__dcSalesMixPayload);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();

  let tries = 0;
  const placementTimer = setInterval(() => {
    tries += 1;
    ensureDetailBlock();
    ensureChartBlock();
    if (window.__dcSalesMixPayload) render(window.__dcSalesMixPayload);
    if (tries > 30 || (byId('paymentBreakdownWrap') && byId('paymentChartPanel'))) clearInterval(placementTimer);
  }, 250);
})();
