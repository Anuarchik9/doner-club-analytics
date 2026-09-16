from flask import request


def install_mobile_responsive_fix(app):
    if getattr(app, "_doner_mobile_responsive_fix_installed", False):
        return
    app._doner_mobile_responsive_fix_installed = True

    @app.after_request
    def _inject_mobile_responsive_fix(response):
        if (
            response.status_code == 200
            and response.mimetype == "text/html"
            and (request.path.endswith("dashboard-v2.html") or request.path.endswith("revisions.html"))
        ):
            try:
                response.direct_passthrough = False
                body = response.get_data(as_text=True)
                tags = ['<script src="/static/mobile-responsive-fix.js?v=20260917-3"></script>']
                if request.path.endswith("revisions.html"):
                    tags.append('<script src="/static/mobile-revisions-overflow-fix.js?v=20260917-1"></script>')
                insertion = ''.join(tags)
                if "mobile-responsive-fix.js" not in body and "</body>" in body:
                    response.set_data(body.replace("</body>", insertion + "</body>", 1))
                    response.headers.pop("Content-Length", None)
            except Exception:
                pass
        return response
