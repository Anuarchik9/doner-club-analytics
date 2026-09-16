from flask import request


def install_chart_hover(app):
    if getattr(app, "_doner_chart_hover_installed", False):
        return
    app._doner_chart_hover_installed = True

    @app.after_request
    def _inject_chart_hover(response):
        if (
            response.status_code == 200
            and response.mimetype == "text/html"
            and request.path.endswith("dashboard-v2.html")
        ):
            try:
                response.direct_passthrough = False
                body = response.get_data(as_text=True)
                tag = '<script src="/static/chart-tooltip.js"></script>'
                if tag not in body and "</body>" in body:
                    response.set_data(body.replace("</body>", tag + "</body>", 1))
                    response.headers.pop("Content-Length", None)
            except Exception:
                pass
        return response
