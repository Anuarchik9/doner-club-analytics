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
    from auth_allowed_users import install_auth_allowlist_patch
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
    from revisions_data_v7 import install_revisions_data_v7
    from progress_ui import install_progress_ui
    from dashboard_category_readability import install_dashboard_category_readability
    from wide_period_click import install_wide_period_click
    from custom_select import install_custom_select
    from mobile_responsive_fix import install_mobile_responsive_fix
    from multi_point import install_multi_point
    from archived_points import install_archived_points
    from point_visibility import install_point_visibility

    # Extend the dashboard allowlist before auth routes start serving requests.
    # Passwords are still validated directly by iikoServer.
    install_auth_allowlist_patch()
    install_auth(worker.wsgi)
    install_revisions_data_v7(worker.wsgi)
    # Register the mobile override first among HTML injectors: Flask runs
    # after_request hooks in reverse order, so this script is injected last
    # and can safely win over older desktop-oriented CSS on iPhones.
    install_mobile_responsive_fix(worker.wsgi)
    # Register dashboard readability/category guard early so its JS is injected
    # after the older dashboard extensions and wins any late category redraws.
    install_dashboard_category_readability(worker.wsgi)
    # Make the full visible date/month fields clickable on both dashboard pages.
    install_wide_period_click(worker.wsgi)
    # Replace native select menus with the same dark custom UI on revisions and sales analytics.
    install_custom_select(worker.wsgi)
    # The first registered after-request extension is injected last into the HTML.
    # Register progress early so its JS executes after the other page extensions.
    install_progress_ui(worker.wsgi)
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
    # Register this before multi-point so its script is injected after the
    # multi-point selector and can remove technical/non-sales options reliably.
    install_point_visibility(worker.wsgi)
    # Install after team-meal so combined sales-mix requests preserve its
    # classification patch, then expose the checkbox point selector.
    install_multi_point(worker.wsgi)
    # Closed points can disappear from the current iikoCloud inventory API even
    # though their historical sales remain available in iikoServer OLAP.
    install_archived_points(worker.wsgi)
    install_speed_patch(worker.wsgi)
    install_chart_hover(worker.wsgi)
    install_preset_controls(worker.wsgi)