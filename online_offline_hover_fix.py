import app as core


def install_online_offline_hover_fix(app):
    if getattr(app, "_doner_online_offline_hover_fix_installed", False):
        return
    app._doner_online_offline_hover_fix_installed = True

    @app.after_request
    def _inject_online_offline_hover_fix(response):
        if (
            response.status_code == 200
            and response.mimetype == "text/html"
            and core.request.path.endswith("dashboard-v2.html")
        ):
            try:
                response.direct_passthrough = False
                body = response.get_data(as_text=True)
                tag = '<script src="/static/online-offline-hover-fix.js?v=20260917-2"></script>'
                if "online-offline-hover-fix.js" not in body and "</body>" in body:
                    response.set_data(body.replace("</body>", tag + "</body>", 1))
                    response.headers.pop("Content-Length", None)
            except Exception:
                pass
        return response
