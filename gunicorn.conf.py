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
    from trend_features import install_trend_features
    from cashier_features import install_cashier_features
    from sales_channel import install_sales_channel
    from team_meal import install_team_meal
    from speed_patch import install_speed_patch
    from chart_hover import install_chart_hover
    from preset_controls import install_preset_controls
    from dashboard_polish import install_dashboard_polish
    from period_notes import install_period_notes
    from ui_upgrade import install_ui_upgrade
    from trend_label_patch import install_trend_label_patch
    from compact_layout import install_compact_layout
    from report_final_polish import install_report_final_polish
    from navigation_shell import install_navigation_shell
    from revisions_ui import install_revisions_ui
    from revisions_data_v2 import install_revisions_data_v2

    install_auth(worker.wsgi)
    install_revisions_data_v2(worker.wsgi)
    # The first registered after-request extension is injected last into the HTML.
    install_revisions_ui(worker.wsgi)
    install_navigation_shell(worker.wsgi)
    install_report_final_polish(worker.wsgi)
    install_compact_layout(worker.wsgi)
    install_trend_label_patch(worker.wsgi)
    install_ui_upgrade(worker.wsgi)
    install_trend_features(worker.wsgi)
    install_period_notes(worker.wsgi)
    install_dashboard_polish(worker.wsgi)
    install_management_features(worker.wsgi)
    install_cashier_features(worker.wsgi)
    install_economics_features(worker.wsgi)
    install_stop_loss(worker.wsgi)
    install_sales_channel(worker.wsgi)
    install_team_meal(worker.wsgi)
    install_speed_patch(worker.wsgi)
    install_chart_hover(worker.wsgi)
    install_preset_controls(worker.wsgi)
