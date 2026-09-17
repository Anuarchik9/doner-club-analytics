"""Dashboard point visibility rules.

Hides technical/non-sales departments from the point selector while keeping
archived sales points such as Манас and Сыганак available for historical reports.
"""

from flask import request


def install_point_visibility(app):
    if getattr(app, "_doner_point_visibility_installed", False):
        return
    app._doner_point_visibility_installed = True

    @app.after_request
    def _inject_point_visibility(response):
        if (
            response.status_code == 200
            and response.mimetype == "text/html"
            and request.path.endswith("dashboard-v2.html")
        ):
            try:
                response.direct_passthrough = False
                body = response.get_data(as_text=True)
                tag = '<script src="/static/point-visibility.js?v=20260917-2"></script>'
                if "point-visibility.js" not in body and "</body>" in body:
                    response.set_data(body.replace("</body>", tag + "</body>", 1))
            except Exception:
                pass
        return response
