(() => {
  if (window.__dcRevisionReadabilityUpsize) return;
  window.__dcRevisionReadabilityUpsize = true;

  const style = document.createElement('style');
  style.textContent = `
    /* Main revision page: use the wide desktop canvas and stop rendering tiny copy. */
    body{font-size:16px!important}
    .wrap{max-width:1760px!important;padding-left:28px!important;padding-right:28px!important}
    .brand b{font-size:16px!important}.brand small{font-size:12.5px!important}
    .source{font-size:12px!important;padding:8px 12px!important}
    .hero{padding-top:44px!important}.eyebrow{font-size:12px!important}
    .hero h1{font-size:clamp(48px,5vw,72px)!important;line-height:.98!important}
    .hero p{font-size:15px!important;line-height:1.65!important;max-width:980px!important}
    .filters{gap:14px!important;padding:18px!important}
    .field label{font-size:11px!important}
    .field select,.field input{height:50px!important;font-size:15px!important;padding:0 14px!important}
    .go{height:50px!important;font-size:15px!important;padding:0 24px!important}
    .section{margin-top:34px!important;margin-bottom:14px!important}
    .section h2{font-size:25px!important}.section .muted{font-size:13px!important}
    .cards{gap:15px!important}.card{padding:22px!important;min-height:154px!important}
    .label{font-size:12.5px!important}.value{font-size:39px!important}.sub{font-size:12.5px!important;line-height:1.55!important}
    .grid{gap:15px!important}.panel{padding:22px!important}.panel h3{font-size:19px!important}.muted{font-size:13px!important;line-height:1.55!important}
    .revision-row{font-size:14px!important;padding:15px 0!important}.revision-row b{font-size:14.5px!important}.pill{font-size:11px!important;padding:6px 10px!important}
    .note{font-size:13px!important;line-height:1.6!important}

    /* Management block added after data loads. */
    #revisionManagement .rev-mgmt-summary{font-size:14px!important;line-height:1.65!important;padding:17px 18px!important}
    #revisionManagement .rev-mgmt-kpis{gap:12px!important}
    #revisionManagement .rev-mgmt-kpi{padding:18px!important;border-radius:16px!important}
    #revisionManagement .rev-mgmt-kpi span{font-size:10.5px!important}
    #revisionManagement .rev-mgmt-kpi b{font-size:22px!important;line-height:1.15!important}
    #revisionManagement .rev-mgmt-kpi small{font-size:11.5px!important;line-height:1.5!important}
    #revisionManagement .rev-mgmt-panel{padding:18px!important}
    #revisionManagement .rev-mgmt-panel h3{font-size:18px!important}
    #revisionManagement .rev-mgmt-panel>p{font-size:11.5px!important;line-height:1.5!important}
    #revisionManagement .rev-mgmt-row{padding:12px 0!important}
    #revisionManagement .rev-mgmt-row b{font-size:13.5px!important}
    #revisionManagement .rev-mgmt-row small{font-size:10.5px!important;line-height:1.45!important}
    #revisionManagement .rev-mgmt-row strong{font-size:13px!important}
    #revisionManagement .rev-mgmt-action{padding:15px!important}
    #revisionManagement .rev-mgmt-action b{font-size:13.5px!important}
    #revisionManagement .rev-mgmt-action span{font-size:11.5px!important;line-height:1.5!important}
    #revisionManagement .rev-mgmt-foot{font-size:10.5px!important;line-height:1.55!important}

    /* Revision accuracy/history table. */
    #revisionAccuracy .rev-accuracy-card{padding:18px!important}
    #revisionAccuracy .rev-accuracy-card span{font-size:10.5px!important}
    #revisionAccuracy .rev-accuracy-card b{font-size:22px!important}
    #revisionAccuracy .rev-accuracy-card small{font-size:11px!important}
    #revisionAccuracy .rev-accuracy-table th{font-size:10px!important;padding:11px 9px!important}
    #revisionAccuracy .rev-accuracy-table td{font-size:11.5px!important;padding:11px 9px!important}
    #revisionAccuracy .rev-accuracy-note{font-size:10.5px!important;line-height:1.55!important}

    /* Product drilldown modal: large readable working surface. */
    .rev-product-drawer{width:min(1540px,calc(100vw - 36px))!important;height:calc(100dvh - 20px)!important;top:10px!important;left:50%!important;right:auto!important;border-radius:22px!important}
    .rev-product-drawer:not(.show){transform:translate(-50%,24px)!important}
    .rev-product-drawer.show{transform:translate(-50%,0)!important}
    .rev-product-head{padding:25px 28px 20px!important}
    .rev-product-head small{font-size:11px!important}.rev-product-head h2{font-size:35px!important}
    .rev-product-close{width:44px!important;height:44px!important;font-size:24px!important;border-radius:14px!important}
    .rev-product-body{padding:25px 28px 40px!important}
    .rev-product-summary{font-size:14px!important;line-height:1.68!important;padding:17px 19px!important}
    .rev-product-kpis{gap:12px!important}.rev-product-kpi{padding:18px!important}
    .rev-product-kpi span{font-size:10.5px!important}.rev-product-kpi b{font-size:27px!important}.rev-product-kpi small{font-size:11.5px!important}
    .rev-product-section{margin-top:26px!important}.rev-product-section h3{font-size:22px!important}
    .rev-product-section-head span,.rev-product-section>p{font-size:12px!important;line-height:1.55!important}
    .rev-product-table{min-width:1080px!important}.rev-product-table th{font-size:10.5px!important;padding:12px 13px!important}.rev-product-table td{font-size:13px!important;padding:13px!important}
    .rev-product-candidate{padding:13px 15px!important}.rev-product-candidate b{font-size:13.5px!important}.rev-product-candidate small{font-size:11px!important}.rev-product-candidate strong{font-size:13.5px!important}
    .rev-product-warning{font-size:11.5px!important;line-height:1.6!important;padding:13px 15px!important}
    .rev-product-action{padding:14px 15px!important}.rev-product-action b{font-size:13.5px!important}.rev-product-action span{font-size:11.5px!important;line-height:1.55!important}

    /* Investigation questions and next-revision protocol. */
    .rev-investigation{padding:20px!important}
    .rev-investigation-head h3,.rev-next-revision h3{font-size:22px!important}
    .rev-investigation-head p,.rev-next-revision p{font-size:12px!important;line-height:1.55!important}
    .rev-investigation-alert{font-size:12.5px!important;line-height:1.65!important;padding:15px 16px!important}
    .rev-question{padding:15px!important}.rev-question-num{width:30px!important;height:30px!important;font-size:11px!important}
    .rev-question b{font-size:13.5px!important;line-height:1.48!important}.rev-question small{font-size:10.5px!important;line-height:1.5!important;margin-top:5px!important}
    .rev-question-check{font-size:10.5px!important}.rev-question-answer{min-height:96px!important;font-size:13px!important;line-height:1.55!important;padding:13px 14px!important}
    .rev-investigation-btn{font-size:11.5px!important;padding:9px 13px!important}
    .rev-protocol-item{padding:14px 15px!important}.rev-protocol-item b{font-size:13px!important}.rev-protocol-item span{font-size:10.5px!important;line-height:1.5!important}
    .rev-investigation-foot{font-size:10.5px!important;line-height:1.55!important}

    @media(max-width:1200px){
      .wrap{padding-left:20px!important;padding-right:20px!important}
      .rev-product-drawer{width:calc(100vw - 22px)!important}
    }
    @media(max-width:900px){
      body{font-size:15px!important}.wrap{padding-left:15px!important;padding-right:15px!important}
      .hero p{font-size:14px!important}.section h2{font-size:22px!important}
    }
    @media(max-width:600px){
      body{font-size:14px!important}.wrap{padding-left:12px!important;padding-right:12px!important}
      .rev-product-drawer{width:calc(100vw - 10px)!important;height:calc(100dvh - 10px)!important;top:5px!important;border-radius:16px!important}
      .rev-product-head{padding:17px 15px 14px!important}.rev-product-head h2{font-size:26px!important}.rev-product-body{padding:17px 15px 26px!important}
      .rev-product-kpis{grid-template-columns:1fr!important}.rev-product-table{min-width:850px!important}
    }
  `;
  document.head.appendChild(style);
})();
