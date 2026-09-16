(() => {
  if (window.__dcRevisionProductModalLarge) return;
  window.__dcRevisionProductModalLarge = true;

  const style = document.createElement('style');
  style.textContent = `
    /* Large centered product analysis modal */
    .rev-product-backdrop{
      background:rgba(0,0,0,.78)!important;
      backdrop-filter:blur(7px)!important;
    }
    .rev-product-drawer{
      left:50%!important;
      right:auto!important;
      top:4dvh!important;
      width:min(1500px,90vw)!important;
      max-width:none!important;
      height:92dvh!important;
      border:1px solid #303030!important;
      border-radius:22px!important;
      box-shadow:0 28px 100px rgba(0,0,0,.68)!important;
      transform:translate(-50%,24px) scale(.99)!important;
      opacity:0!important;
      transition:transform .22s ease,opacity .18s ease!important;
      overflow:auto!important;
    }
    .rev-product-drawer.show{
      transform:translate(-50%,0) scale(1)!important;
      opacity:1!important;
    }

    .rev-product-head{
      padding:24px 30px 20px!important;
      background:rgba(11,11,11,.97)!important;
    }
    .rev-product-head small{
      font-size:10px!important;
      margin-bottom:7px!important;
    }
    .rev-product-head h2{
      font-size:34px!important;
      line-height:1.08!important;
    }
    .rev-product-close{
      width:44px!important;
      height:44px!important;
      flex:0 0 44px!important;
      border-radius:13px!important;
      font-size:25px!important;
    }
    .rev-product-body{
      padding:26px 30px 42px!important;
      max-width:none!important;
    }
    .rev-product-summary{
      padding:17px 19px!important;
      font-size:13px!important;
      line-height:1.65!important;
      border-radius:16px!important;
    }

    .rev-product-kpis{
      gap:12px!important;
      margin-top:13px!important;
    }
    .rev-product-kpi{
      padding:17px 17px!important;
      min-height:108px!important;
      border-radius:16px!important;
    }
    .rev-product-kpi span{
      font-size:9px!important;
    }
    .rev-product-kpi b{
      margin-top:8px!important;
      font-size:24px!important;
      line-height:1.12!important;
    }
    .rev-product-kpi small{
      margin-top:6px!important;
      font-size:10px!important;
      line-height:1.45!important;
    }

    .rev-product-diagnostic{
      margin-top:13px!important;
      padding:15px 17px!important;
      font-size:12px!important;
      line-height:1.6!important;
      border-radius:15px!important;
    }
    .rev-product-section{
      margin-top:26px!important;
    }
    .rev-product-section-head{
      margin-bottom:11px!important;
    }
    .rev-product-section h3{
      font-size:19px!important;
      line-height:1.2!important;
    }
    .rev-product-section-head span,
    .rev-product-section>p{
      font-size:11px!important;
      line-height:1.5!important;
      margin-top:5px!important;
    }

    .rev-product-table-wrap{
      border-radius:16px!important;
    }
    .rev-product-table{
      width:100%!important;
      min-width:1040px!important;
    }
    .rev-product-table th{
      padding:11px 13px!important;
      font-size:9px!important;
      letter-spacing:.055em!important;
    }
    .rev-product-table td{
      padding:12px 13px!important;
      font-size:12px!important;
      line-height:1.35!important;
    }
    .rev-product-table .doc-name{max-width:250px!important}
    .rev-product-table .store-name{max-width:220px!important}
    .rev-product-doc-note{
      margin-top:10px!important;
      font-size:11px!important;
      line-height:1.55!important;
    }

    .rev-product-candidates{
      gap:9px!important;
      margin-top:11px!important;
    }
    .rev-product-candidate{
      padding:13px 14px!important;
      border-radius:14px!important;
    }
    .rev-product-candidate b{
      font-size:13px!important;
    }
    .rev-product-candidate small{
      font-size:10px!important;
      line-height:1.45!important;
      margin-top:4px!important;
    }
    .rev-product-candidate strong{
      font-size:13px!important;
    }
    .rev-product-warning{
      padding:13px 14px!important;
      font-size:11px!important;
      line-height:1.6!important;
      border-radius:14px!important;
    }

    .rev-product-actions{
      gap:10px!important;
      margin-top:11px!important;
    }
    .rev-product-action{
      grid-template-columns:30px minmax(0,1fr)!important;
      gap:12px!important;
      padding:14px 15px!important;
      border-radius:14px!important;
    }
    .rev-product-action i{
      width:30px!important;
      height:30px!important;
      border-radius:9px!important;
      font-size:10px!important;
    }
    .rev-product-action b{
      font-size:12px!important;
    }
    .rev-product-action span{
      font-size:10.5px!important;
      line-height:1.55!important;
      margin-top:4px!important;
    }

    @media(max-width:1250px){
      .rev-product-drawer{
        width:calc(100vw - 32px)!important;
        height:calc(100dvh - 28px)!important;
        top:14px!important;
      }
      .rev-product-kpis{grid-template-columns:1fr 1fr!important}
      .rev-product-head h2{font-size:30px!important}
    }
    @media(max-width:760px){
      .rev-product-drawer{
        width:calc(100vw - 12px)!important;
        height:calc(100dvh - 12px)!important;
        top:6px!important;
        border-radius:16px!important;
      }
      .rev-product-head{padding:17px 14px 14px!important}
      .rev-product-head h2{font-size:25px!important}
      .rev-product-close{width:38px!important;height:38px!important;flex-basis:38px!important}
      .rev-product-body{padding:16px 14px 28px!important}
      .rev-product-summary{font-size:12px!important;padding:14px!important}
      .rev-product-kpis{grid-template-columns:1fr!important}
      .rev-product-kpi{min-height:auto!important}
      .rev-product-kpi b{font-size:21px!important}
      .rev-product-table{min-width:850px!important}
      .rev-product-table td{font-size:11px!important}
      .rev-product-section h3{font-size:17px!important}
    }
  `;
  document.head.appendChild(style);
})();
