from flask import request


def install_wide_period_click(app):
    if getattr(app, "_doner_wide_period_click_installed", False):
        return
    app._doner_wide_period_click_installed = True

    @app.after_request
    def _inject_wide_period_click(response):
        if (
            response.status_code == 200
            and response.mimetype == "text/html"
            and (request.path.endswith("dashboard-v2.html") or request.path.endswith("revisions.html"))
        ):
            try:
                response.direct_passthrough = False
                body = response.get_data(as_text=True)
                tag = '<script src="/static/wide-period-click.js?v=20260916-3"></script>'
                if "wide-period-click.js" not in body and "</body>" in body:
                    response.set_data(body.replace("</body>", tag + "</body>", 1))
                    response.headers.pop("Content-Length", None)
            except Exception:
                pass
        return response
