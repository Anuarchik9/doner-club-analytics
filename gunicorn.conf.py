# The dashboard makes several independent iiko/iikoCloud requests in parallel.
# gthread lets one Render instance process those network-bound requests concurrently
# instead of queueing them one-by-one behind a single synchronous worker.
worker_class = "gthread"
workers = 1
threads = 8
timeout = 120
keepalive = 5


def post_worker_init(worker):
    from dashboard_auth import install_auth
    from sales_channel import install_sales_channel
    from team_meal import install_team_meal
    from speed_patch import install_speed_patch
    from chart_hover import install_chart_hover
    from preset_controls import install_preset_controls

    install_auth(worker.wsgi)
    install_sales_channel(worker.wsgi)
    install_team_meal(worker.wsgi)
    install_speed_patch(worker.wsgi)
    install_chart_hover(worker.wsgi)
    install_preset_controls(worker.wsgi)
