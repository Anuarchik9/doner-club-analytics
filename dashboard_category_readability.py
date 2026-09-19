from flask import request


_CRITICAL_DASHBOARD_STYLE = r'''<style id="dc-dashboard-critical-layout">
/* Critical first-paint layout. Keep this in the HTML head so the dashboard opens
   immediately at its final desktop size instead of first painting the old 1420px
   / 14px layout and then growing after JavaScript loads. */
@media (min-width: 901px) {
  body{font-size:16px!important}
  .wrap{max-width:1760px!important;padding-left:28px!important;padding-right:28px!important}
  .hero h1{font-size:58px!important;line-height:1.04!important}
  .hero #period{font-size:14px!important}
  .section{margin-top:36px!important;margin-bottom:15px!important}
  .section h2{font-size:26px!important;line-height:1.15!important}
  .section>.muted,.muted{font-size:13px!important;line-height:1.55!important}
  .panel{padding:24px!important}
  .panel h3{font-size:19px!important;line-height:1.2!important}
  .filters{gap:15px!important;padding:19px!important}
  .field label{font-size:11.5px!important}
  .field select,.field input,.dc-picker-trigger,.dc-select-trigger{height:52px!important;font-size:15px!important;padding-left:15px!important;padding-right:15px!important}
  .go{height:52px!important;font-size:15px!important;padding-left:25px!important;padding-right:25px!important}
  .preset,.report-mode-btn{font-size:13.5px!important;padding:9px 14px!important}
  .label{font-size:12.5px!important}
  .value{font-size:42px!important}
  .sub{font-size:12.5px!important;line-height:1.55!important}
}
@media (min-width:901px) and (max-width:1200px){
  .wrap{padding-left:22px!important;padding-right:22px!important}
  .hero h1{font-size:52px!important}
}
</style>'''


def install_dashboard_category_readability(app):
    if getattr(app, "_doner_dashboard_category_readability_installed", False):
        return
    app._doner_dashboard_category_readability_installed = True

    @app.after_request
    def _inject_dashboard_category_readability(response):
        if (
            response.status_code == 200
            and response.mimetype == "text/html"
            and request.path.endswith("dashboard-v2.html")
        ):
            try:
                response.direct_passthrough = False
                body = response.get_data(as_text=True)
                changed = False

                if "dc-dashboard-critical-layout" not in body and "</head>" in body:
                    body = body.replace("</head>", _CRITICAL_DASHBOARD_STYLE + "</head>", 1)
                    changed = True

                # Single authoritative dashboard category script. Older separate
                # category patches are intentionally not injected anymore because
                # two MutationObservers were repeatedly rebuilding the same rows.
                readability_tag = '<script src="/static/dashboard-category-readability.js?v=20260919-1"></script>'
                if "dashboard-category-readability.js" not in body and "</body>" in body:
                    body = body.replace("</body>", readability_tag + "</body>", 1)
                    changed = True

                if changed:
                    response.set_data(body)
                    response.headers.pop("Content-Length", None)
            except Exception:
                pass
        return response
