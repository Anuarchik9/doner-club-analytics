from flask import request


def install_progress_ui(app):
    if getattr(app, "_doner_progress_ui_installed", False):
        return
    app._doner_progress_ui_installed = True

    @app.after_request
    def _inject_progress_ui(response):
        if (
            response.status_code == 200
            and response.mimetype == "text/html"
            and (
                request.path.endswith("dashboard-v2.html")
                or request.path.endswith("revisions.html")
            )
        ):
            try:
                response.direct_passthrough = False
                body = response.get_data(as_text=True)
                tag = '<script src="/static/smart-progress.js?v=20260916-1"></script>'
                if "/static/smart-progress.js" not in body and "</body>" in body:
                    response.set_data(body.replace("</body>", tag + "</body>", 1))
                    response.headers.pop("Content-Length", None)
            except Exception:
                pass
        return response
