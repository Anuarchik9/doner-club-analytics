from flask import request


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
                tag = '<script src="/static/dashboard-category-readability.js?v=20260916-3"></script>'
                if "dashboard-category-readability.js" not in body and "</body>" in body:
                    response.set_data(body.replace("</body>", tag + "</body>", 1))
                    response.headers.pop("Content-Length", None)
            except Exception:
                pass
        return response
