(() => {
  if (window.__dcMobileRevisionsOverflowFix) return;
  window.__dcMobileRevisionsOverflowFix = true;
  if (!location.pathname.endsWith('/revisions.html')) return;

  document.documentElement.classList.add('dc-mobile-revisions-overflow-fixed');

  const style = document.createElement('style');
  style.textContent = `
    @media (max-width: 767px) {
      .dc-mobile-revisions body,
      .dc-mobile-revisions body > .wrap,
      .dc-mobile-revisions .wrap {
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        overflow-x: hidden !important;
      }

      .dc-mobile-revisions .wrap > *,
      .dc-mobile-revisions .grid,
      .dc-mobile-revisions .panel,
      .dc-mobile-revisions #revisionInsights,
      .dc-mobile-revisions .rev-insights,
      .dc-mobile-revisions .rev-insights-grid,
      .dc-mobile-revisions .rev-side,
      .dc-mobile-revisions .rev-trend-panel,
      .dc-mobile-revisions .rev-signal-panel,
      .dc-mobile-revisions .rev-problems-panel,
      .dc-mobile-revisions #revisionManagement,
      .dc-mobile-revisions .rev-management,
      .dc-mobile-revisions .rev-management-kpis,
      .dc-mobile-revisions .rev-management-grid,
      .dc-mobile-revisions .rev-actions,
      .dc-mobile-revisions .rev-mgmt-panel,
      .dc-mobile-revisions .rev-accuracy-grid,
      .dc-mobile-revisions .rev-accuracy-panel,
      .dc-mobile-revisions .rev-accuracy-table-wrap {
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        box-sizing: border-box !important;
      }

      .dc-mobile-revisions .grid,
      .dc-mobile-revisions .rev-insights-grid,
      .dc-mobile-revisions .rev-side,
      .dc-mobile-revisions .rev-management-kpis,
      .dc-mobile-revisions .rev-management-grid,
      .dc-mobile-revisions .rev-actions,
      .dc-mobile-revisions .rev-accuracy-grid {
        display: grid !important;
        grid-template-columns: minmax(0, 1fr) !important;
        gap: 10px !important;
      }

      .dc-mobile-revisions .panel,
      .dc-mobile-revisions .rev-trend-panel,
      .dc-mobile-revisions .rev-signal-panel,
      .dc-mobile-revisions .rev-problems-panel,
      .dc-mobile-revisions .rev-mgmt-panel,
      .dc-mobile-revisions .rev-accuracy-panel {
        overflow: hidden !important;
      }

      .dc-mobile-revisions .rev-trend-head {
        width: 100% !important;
        min-width: 0 !important;
        flex-direction: column !important;
        align-items: flex-start !important;
        gap: 10px !important;
      }
      .dc-mobile-revisions .rev-legend {
        width: 100% !important;
        max-width: 100% !important;
        flex-wrap: wrap !important;
      }
      .dc-mobile-revisions .rev-chart-wrap {
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        overflow: hidden !important;
        min-height: 0 !important;
      }
      .dc-mobile-revisions .rev-chart-wrap svg {
        display: block !important;
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        height: auto !important;
        overflow: hidden !important;
      }
      .dc-mobile-revisions .rev-chart-note,
      .dc-mobile-revisions .rev-insights-title span {
        width: 100% !important;
        max-width: 100% !important;
        white-space: normal !important;
        overflow-wrap: anywhere !important;
      }

      .dc-mobile-revisions .rev-signals,
      .dc-mobile-revisions .rev-problems,
      .dc-mobile-revisions .rev-signal,
      .dc-mobile-revisions .rev-problem {
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
      }
      .dc-mobile-revisions .rev-signal b,
      .dc-mobile-revisions .rev-signal span,
      .dc-mobile-revisions .rev-problem b,
      .dc-mobile-revisions .rev-problem small,
      .dc-mobile-revisions .rev-problem strong {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
        overflow-wrap: anywhere !important;
      }
      .dc-mobile-revisions .rev-problem {
        grid-template-columns: minmax(0,1fr) !important;
        gap: 4px !important;
      }
      .dc-mobile-revisions .rev-problem strong {
        justify-self: start !important;
      }
      .dc-mobile-revisions .rev-problem-more {
        max-width: 100% !important;
        white-space: normal !important;
      }

      .dc-mobile-revisions .rev-management-head {
        width: 100% !important;
        min-width: 0 !important;
        flex-direction: column !important;
        align-items: flex-start !important;
      }
      .dc-mobile-revisions .rev-management-head span,
      .dc-mobile-revisions .rev-management-summary,
      .dc-mobile-revisions .rev-mgmt-note,
      .dc-mobile-revisions .rev-action,
      .dc-mobile-revisions .rev-action span {
        max-width: 100% !important;
        white-space: normal !important;
        overflow-wrap: anywhere !important;
      }
      .dc-mobile-revisions .rev-mgmt-row {
        width: 100% !important;
        min-width: 0 !important;
        grid-template-columns: minmax(0,1fr) !important;
        gap: 5px !important;
      }
      .dc-mobile-revisions .rev-mgmt-row b,
      .dc-mobile-revisions .rev-mgmt-row small,
      .dc-mobile-revisions .rev-mgmt-row strong {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
        overflow-wrap: anywhere !important;
      }
      .dc-mobile-revisions .rev-mgmt-row strong { justify-self: start !important; }

      .dc-mobile-revisions .revision-history {
        display: block !important;
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        margin-top: 12px !important;
        border-collapse: separate !important;
      }
      .dc-mobile-revisions .revision-history thead { display: none !important; }
      .dc-mobile-revisions .revision-history tbody {
        display: grid !important;
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        gap: 10px !important;
      }
      .dc-mobile-revisions .revision-history tr {
        display: block !important;
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        padding: 13px 14px !important;
        border: 1px solid #292929 !important;
        border-radius: 14px !important;
        background: #0d0d0d !important;
      }
      .dc-mobile-revisions .revision-history td {
        display: block !important;
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        border: 0 !important;
        padding: 6px 0 !important;
        text-align: left !important;
        white-space: normal !important;
        overflow-wrap: anywhere !important;
      }
      .dc-mobile-revisions .revision-history td:first-child {
        padding-bottom: 10px !important;
        border-bottom: 1px solid #222 !important;
        margin-bottom: 3px !important;
      }
      .dc-mobile-revisions .revision-history td.num {
        display: grid !important;
        grid-template-columns: minmax(0,1fr) auto !important;
        align-items: baseline !important;
        gap: 12px !important;
        font-weight: 800 !important;
      }
      .dc-mobile-revisions .revision-history td.num::before {
        color: #7f7f79 !important;
        font-size: 10px !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        letter-spacing: .05em !important;
      }
      .dc-mobile-revisions .revision-history td:nth-child(2)::before { content: 'Недостача'; }
      .dc-mobile-revisions .revision-history td:nth-child(3)::before { content: 'Излишки'; }
      .dc-mobile-revisions .revision-history td:nth-child(4)::before { content: 'Оборот'; }
      .dc-mobile-revisions .revision-history td:nth-child(5)::before { content: 'Итог'; }
      .dc-mobile-revisions .revision-history .rev-small {
        width: 100% !important;
        max-width: 100% !important;
        white-space: normal !important;
        overflow-wrap: anywhere !important;
        line-height: 1.45 !important;
      }

      .dc-mobile-revisions .rev-accuracy-table-wrap {
        display: block !important;
        overflow-x: auto !important;
        overflow-y: hidden !important;
        -webkit-overflow-scrolling: touch !important;
        overscroll-behavior-inline: contain !important;
        contain: inline-size !important;
      }
      .dc-mobile-revisions .rev-accuracy-table {
        width: 720px !important;
        min-width: 720px !important;
        max-width: none !important;
      }

      .dc-mobile-revisions .revision-row,
      .dc-mobile-revisions .rev-list-block,
      .dc-mobile-revisions .rev-list-item {
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
      }
      .dc-mobile-revisions .rev-list-item {
        grid-template-columns: minmax(0,1fr) !important;
        gap: 3px !important;
      }
      .dc-mobile-revisions .rev-list-item span:first-child,
      .dc-mobile-revisions .rev-list-item b {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
        overflow-wrap: anywhere !important;
      }

      .dc-mobile-revisions [class^='rev-'],
      .dc-mobile-revisions [class*=' rev-'] {
        box-sizing: border-box;
      }
    }

    @media (max-width: 390px) {
      .dc-mobile-revisions .revision-history tr { padding: 12px !important; }
      .dc-mobile-revisions .revision-history td.num {
        grid-template-columns: minmax(0,1fr) auto !important;
        gap: 8px !important;
      }
    }
  `;

  document.head.appendChild(style);
})();