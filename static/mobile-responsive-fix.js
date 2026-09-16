(() => {
  if (window.__dcMobileResponsiveFix) return;
  window.__dcMobileResponsiveFix = true;

  const style = document.createElement('style');
  style.textContent = `
    @media (max-width: 767px) {
      html, body {
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        overflow-x: hidden !important;
        -webkit-text-size-adjust: 100%;
      }
      body { position: relative; }
      body > .wrap,
      .wrap {
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        margin: 0 !important;
        padding-left: 12px !important;
        padding-right: 12px !important;
        overflow: visible !important;
      }

      .wrap > *,
      .top,.hero,.filters,.presets,.section,.cards,.grid,.panel,.card,
      .insights,.pulse-grid,.hour-summary,.category-list,.bars,.trend-panel,
      .doner-mix-grid,.meat-cards,.size-list,.tablebox,
      #categoryList,#stopItems,.econ-table-wrap {
        min-width: 0 !important;
        max-width: 100% !important;
        box-sizing: border-box !important;
      }

      .top {
        width: 100% !important;
        height: 64px !important;
        padding-left: 48px !important;
        gap: 8px !important;
      }
      .top .brand { min-width: 0 !important; }
      .top .brand span { display: none !important; }
      .top .logo { width: 40px !important; height: 40px !important; flex-basis: 40px !important; border-radius: 12px !important; }
      .top .live, .source { font-size: 10px !important; padding: 6px 8px !important; white-space: nowrap !important; }

      .hero {
        width: 100% !important;
        display: block !important;
        padding: 28px 0 18px !important;
      }
      .hero h1 {
        font-size: clamp(36px, 11vw, 46px) !important;
        line-height: 1.02 !important;
        margin: 8px 0 10px !important;
        overflow-wrap: anywhere !important;
      }
      .hero #period,
      .hero p,
      #updated {
        max-width: 100% !important;
        font-size: 12px !important;
        line-height: 1.5 !important;
        overflow-wrap: anywhere !important;
      }
      #updated { margin-top: 6px !important; }

      .filters,
      .filters.dc-month-mode {
        width: 100% !important;
        display: grid !important;
        grid-template-columns: minmax(0,1fr) !important;
        gap: 10px !important;
        padding: 12px !important;
        border-radius: 16px !important;
      }
      .filters .field,
      .filters .field:first-child,
      .filters .go,
      .dc-sales-month-field {
        width: 100% !important;
        min-width: 0 !important;
        max-width: 100% !important;
        grid-column: auto !important;
      }
      .field select,.field input,
      .dc-picker-trigger,.dc-select-trigger,.go {
        width: 100% !important;
        min-width: 0 !important;
        max-width: 100% !important;
      }
      .field select,.field input,.dc-picker-trigger,.dc-select-trigger,.go {
        height: 48px !important;
        font-size: 14px !important;
      }
      .go { display: block !important; }

      .presets {
        width: 100% !important;
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 7px !important;
        margin: 10px 0 24px !important;
      }
      .preset,.report-mode-btn {
        flex: 0 0 auto !important;
        max-width: 100% !important;
        padding: 8px 11px !important;
        font-size: 11.5px !important;
      }

      .section {
        width: 100% !important;
        display: flex !important;
        flex-wrap: wrap !important;
        align-items: flex-start !important;
        gap: 6px 10px !important;
        margin-top: 27px !important;
      }
      .section h2 { font-size: 21px !important; }
      .section > .muted { width: 100% !important; font-size: 11px !important; }

      .cards,.grid,.insights,.pulse-grid,.hour-summary,.doner-mix-grid,.meat-cards {
        width: 100% !important;
        display: grid !important;
        grid-template-columns: minmax(0,1fr) !important;
        gap: 10px !important;
      }
      .card,.panel,.insight,.pulse-card,.hour-stat,.meat-card {
        width: 100% !important;
        min-width: 0 !important;
        max-width: 100% !important;
      }
      .card { min-height: 132px !important; padding: 17px !important; }
      .panel { padding: 16px !important; border-radius: 16px !important; }
      .value { font-size: 32px !important; white-space: normal !important; overflow-wrap: anywhere !important; }

      .channel-mix-card,
      .dc-offline-card,
      .dc-online-card {
        width: 100% !important;
        max-width: 100% !important;
        padding-right: 16px !important;
      }
      .channel-mix-card { padding-bottom: 92px !important; }
      .dc-offline-card { padding-bottom: 118px !important; }
      .dc-mix-icons,
      .dc-offline-card .dc-mix-icons {
        left: 16px !important;
        right: 16px !important;
        width: auto !important;
        max-width: calc(100% - 32px) !important;
      }

      #categoryList { width: 100% !important; }
      #categoryList .cat-row,
      .cat-row {
        width: 100% !important;
        min-width: 0 !important;
        grid-template-columns: minmax(0,1fr) !important;
        gap: 8px !important;
      }
      #categoryList .cat-name,
      #categoryList .track,
      #categoryList .cat-share {
        width: 100% !important;
        min-width: 0 !important;
        max-width: 100% !important;
      }
      #categoryList .cat-share { text-align: left !important; }
      #categoryList .dc-other-audit { max-width: 100% !important; overflow-wrap: anywhere !important; }

      .trend-head { flex-direction: column !important; }
      .legend { width: 100% !important; }
      .chart-wrap,
      .dc-line-chart,
      .hour-line-chart {
        width: 100% !important;
        max-width: 100% !important;
        overflow: hidden !important;
      }
      .chart-wrap svg { max-width: 100% !important; overflow: hidden !important; }

      .heat-grid { grid-template-columns: repeat(2,minmax(0,1fr)) !important; gap: 8px !important; }
      .heat-cell { min-width: 0 !important; padding: 10px !important; }

      .tablebox,
      .econ-table-wrap {
        width: 100% !important;
        max-width: 100% !important;
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch;
      }
      .tablebox table,
      .econ-table-wrap table {
        width: max-content !important;
        max-width: none !important;
      }

      .search { width: 100% !important; max-width: 100% !important; }

      .dc-picker-panel,
      .dc-select-panel {
        width: calc(100vw - 20px) !important;
        max-width: calc(100vw - 20px) !important;
        left: 10px !important;
        right: auto !important;
      }

      #dc-auth-badge {
        right: max(10px, env(safe-area-inset-right)) !important;
        bottom: max(10px, env(safe-area-inset-bottom)) !important;
        max-width: calc(100vw - 20px) !important;
      }

      /* Revisions page uses the same mobile width rules. */
      .rev-product-drawer {
        width: calc(100vw - 10px) !important;
        max-width: calc(100vw - 10px) !important;
        left: 50% !important;
        right: auto !important;
      }
      .rev-product-body,.rev-product-head { min-width: 0 !important; max-width: 100% !important; }
      .rev-product-kpis { grid-template-columns: minmax(0,1fr) !important; }
      .rev-investigation-grid,.rev-protocol-grid { grid-template-columns: minmax(0,1fr) !important; }
    }

    @media (max-width: 390px) {
      .wrap { padding-left: 10px !important; padding-right: 10px !important; }
      .heat-grid { grid-template-columns: minmax(0,1fr) !important; }
      .dc-brand-badge { font-size: 9px !important; }
    }
  `;
  document.head.appendChild(style);
})();
