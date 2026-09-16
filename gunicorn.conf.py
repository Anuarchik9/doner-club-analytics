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
    from management_features import install_management_features
    from economics_features import install_economics_features
    from stop_loss import install_stop_loss
    from sales_channel import install_sales_channel
    from team_meal import install_team_meal
    from speed_patch import install_speed_patch
    from chart_hover import install_chart_hover
    from preset_controls import install_preset_controls
    from dashboard_polish import install_dashboard_polish

    install_auth(worker.wsgi)
    # Register dashboard extensions before the display patches.
    install_management_features(worker.wsgi)
    install_economics_features(worker.wsgi)
    install_stop_loss(worker.wsgi)
    install_sales_channel(worker.wsgi)
    install_team_meal(worker.wsgi)
    install_speed_patch(worker.wsgi)
    install_chart_hover(worker.wsgi)
    install_preset_controls(worker.wsgi)
    install_dashboard_polish(worker.wsgi)
