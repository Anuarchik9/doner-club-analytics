from flask import request


def install_preset_controls(app):
    if getattr(app, "_doner_preset_controls_installed", False):
        return
    app._doner_preset_controls_installed = True

    @app.after_request
    def _inject_preset_controls(response):
        if (
            response.status_code == 200
            and response.mimetype == "text/html"
            and request.path.endswith("dashboard-v2.html")
        ):
            try:
                response.direct_passthrough = False
                body = response.get_data(as_text=True)
                tag = '<script src="/static/preset-controls.js?v=20260917-3"></script>'
                if "preset-controls.js" not in body and "</body>" in body:
                    response.set_data(body.replace("</body>", tag + "</body>", 1))
                    response.headers.pop("Content-Length", None)
            except Exception:
                pass
        return response
