from flask import request


def install_revisions_ui(app):
    if getattr(app, "_doner_revisions_ui_installed", False):
        return
    app._doner_revisions_ui_installed = True

    @app.after_request
    def _inject_revisions_ui(response):
        if (
            response.status_code == 200
            and response.mimetype == "text/html"
            and request.path.endswith("revisions.html")
        ):
            try:
                response.direct_passthrough = False
                body = response.get_data(as_text=True)
                tags = (
                    '<script src="/static/revision-details.js?v=20260916-2"></script>'
                    '<script src="/static/revision-insights.js?v=20260916-1"></script>'
                    '<script src="/static/revision-balance.js?v=20260916-1"></script>'
                    '<script src="/static/revision-audit.js?v=20260916-1"></script>'
                    '<script src="/static/revision-management.js?v=20260916-1"></script>'
                    '<script src="/static/revision-product-drilldown.js?v=20260916-2"></script>'
                    '<script src="/static/revision-product-diagnostic.js?v=20260916-2"></script>'
                    '<script src="/static/revision-product-modal-large.js?v=20260916-2"></script>'
                    '<script src="/static/revision-product-modal-fix.js?v=20260916-2"></script>'
                    '<script src="/static/revision-investigation.js?v=20260916-2"></script>'
                    '<script src="/static/revision-product-close-hardfix.js?v=20260916-1"></script>'
                    '<script src="/static/revisions-ui.js?v=20260916-6"></script>'
                )
                if "/static/revision-details.js" not in body and "</body>" in body:
                    response.set_data(body.replace("</body>", tags + "</body>", 1))
                    response.headers.pop("Content-Length", None)
            except Exception:
                pass
        return response