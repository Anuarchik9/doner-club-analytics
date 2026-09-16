(() => {
  if (window.__dcNavigationShell) return;
  window.__dcNavigationShell = true;

  const style = document.createElement('style');
  style.textContent = `
    .dc-nav-toggle{position:fixed;left:18px;top:18px;z-index:10020;width:46px;height:46px;border:1px solid #2b2b2b;border-radius:14px;background:rgba(12,12,12,.94);color:#fff;display:grid;place-items:center;cursor:pointer;box-shadow:0 10px 30px rgba(0,0,0,.35);backdrop-filter:blur(14px)}
    .dc-nav-toggle:hover{border-color:#ff5a1f;background:#15100e}
    .dc-nav-toggle span,.dc-nav-toggle span:before,.dc-nav-toggle span:after{display:block;width:19px;height:2px;border-radius:4px;background:#f4f4ef;content:"";position:relative;transition:.2s ease}
    .dc-nav-toggle span:before{position:absolute;left:0;top:-6px}.dc-nav-toggle span:after{position:absolute;left:0;top:6px}
    .dc-nav-toggle.open span{background:transparent}.dc-nav-toggle.open span:before{top:0;transform:rotate(45deg)}.dc-nav-toggle.open span:after{top:0;transform:rotate(-45deg)}
    .dc-nav-backdrop{position:fixed;inset:0;z-index:10010;background:rgba(0,0,0,.46);opacity:0;pointer-events:none;transition:.2s ease}
    .dc-nav-backdrop.open{opacity:1;pointer-events:auto}
    .dc-nav-drawer{position:fixed;z-index:10015;left:0;top:0;bottom:0;width:min(310px,86vw);padding:86px 18px 22px;background:linear-gradient(180deg,#0d0d0d,#080808);border-right:1px solid #242424;box-shadow:24px 0 60px rgba(0,0,0,.4);transform:translateX(-102%);transition:.24s ease;display:flex;flex-direction:column}
    .dc-nav-drawer.open{transform:translateX(0)}
    .dc-nav-brand{padding:0 10px 18px;border-bottom:1px solid #242424;margin-bottom:14px}.dc-nav-brand b{display:block;font-size:15px;letter-spacing:.03em}.dc-nav-brand span{display:block;margin-top:4px;color:#777;font-size:11px}
    .dc-nav-links{display:grid;gap:7px}.dc-nav-link{display:flex;align-items:center;gap:11px;padding:13px 14px;border:1px solid transparent;border-radius:13px;color:#b8b8b3;text-decoration:none;font-weight:800}.dc-nav-link:hover{background:#121212;color:#fff;border-color:#262626}.dc-nav-link.active{background:rgba(255,90,31,.11);color:#fff;border-color:rgba(255,90,31,.42)}
    .dc-nav-icon{width:28px;height:28px;border-radius:9px;background:#171717;display:grid;place-items:center;color:#ff6a32;font-size:14px;flex:0 0 28px}.dc-nav-link.active .dc-nav-icon{background:#ff5a1f;color:#fff}
    .dc-nav-foot{margin-top:auto;padding:16px 10px 0;border-top:1px solid #202020;color:#666;font-size:10px;line-height:1.5}
    @media(max-width:600px){.dc-nav-toggle{left:12px;top:12px;width:42px;height:42px;border-radius:12px}.dc-nav-drawer{padding-top:72px}}
  `;
  document.head.appendChild(style);

  const isRevision = location.pathname.endsWith('/revisions.html');
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'dc-nav-toggle';
  button.setAttribute('aria-label','Открыть меню');
  button.setAttribute('aria-expanded','false');
  button.innerHTML = '<span></span>';

  const backdrop = document.createElement('div');
  backdrop.className = 'dc-nav-backdrop';

  const drawer = document.createElement('aside');
  drawer.className = 'dc-nav-drawer';
  drawer.setAttribute('aria-label','Навигация Doner Club Analytics');
  drawer.innerHTML = `
    <div class="dc-nav-brand"><b>DONER CLUB ANALYTICS</b><span>Управленческая система</span></div>
    <nav class="dc-nav-links">
      <a class="dc-nav-link ${isRevision?'':'active'}" href="/static/dashboard-v2.html"><span class="dc-nav-icon">↗</span><span>Продажи и аналитика</span></a>
      <a class="dc-nav-link ${isRevision?'active':''}" href="/static/revisions.html"><span class="dc-nav-icon">≋</span><span>Ревизии</span></a>
    </nav>
    <div class="dc-nav-foot">Новые управленческие разделы будем добавлять сюда отдельно, не перегружая основной дашборд.</div>`;

  function setOpen(open){
    button.classList.toggle('open',open);
    backdrop.classList.toggle('open',open);
    drawer.classList.toggle('open',open);
    button.setAttribute('aria-expanded',open?'true':'false');
    document.documentElement.style.overflow = open ? 'hidden' : '';
  }
  button.addEventListener('click',()=>setOpen(!drawer.classList.contains('open')));
  backdrop.addEventListener('click',()=>setOpen(false));
  document.addEventListener('keydown',e=>{if(e.key==='Escape')setOpen(false)});

  document.body.appendChild(backdrop);
  document.body.appendChild(drawer);
  document.body.appendChild(button);
})();
