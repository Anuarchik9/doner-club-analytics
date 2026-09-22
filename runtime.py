"""Shared initialization for Gunicorn and local Flask runs."""


def install_runtime(app):
    if getattr(app, "_analytics_runtime_installed", False):
        return
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
    from online_offline_trends import install_online_offline_trends
    from online_offline_hover_fix import install_online_offline_hover_fix
    from telegram_bot import install_telegram_bot
    from procurement_diagnostics import install_procurement_diagnostics
    from staff_diagnostics import install_staff_diagnostics
    from staff_analytics import install_staff_analytics

    # Extend the dashboard allowlist before auth routes start serving requests.
    # Passwords are still validated directly by iikoServer.
    install_auth_allowlist_patch()
    install_auth(app)
    install_revisions_data_v7(app)
    # Register the mobile override first among HTML injectors: Flask runs
    # after_request hooks in reverse order, so this script is injected last
    # and can safely win over older desktop-oriented CSS on iPhones.
    install_mobile_responsive_fix(app)
    # Register dashboard readability/category guard early so its JS is injected
    # after the older dashboard extensions and wins any late category redraws.
    install_dashboard_category_readability(app)
    # Make the full visible date/month fields clickable on both dashboard pages.
    install_wide_period_click(app)
    # Replace native select menus with the same dark custom UI on revisions and sales analytics.
    install_custom_select(app)
    # The first registered after-request extension is injected last into the HTML.
    # Register progress early so its JS executes after the other page extensions.
    install_progress_ui(app)
    install_revisions_ui(app)
    install_navigation_shell(app)
    install_report_final_polish(app)
    install_compact_layout(app)
    install_trend_label_patch(app)
    install_ui_upgrade(app)
    install_trend_features(app)
    install_period_notes(app)
    install_dashboard_polish(app)
    install_management_features(app)
    install_cashier_features(app)
    install_economics_features(app)
    install_stop_loss(app)
    install_sales_channel(app)
    install_team_meal(app)
    # Register this before multi-point so its script is injected after the
    # multi-point selector and can remove technical/non-sales options reliably.
    install_point_visibility(app)
    # Install after team-meal so combined sales-mix requests preserve its
    # classification patch, then expose the checkbox point selector.
    install_multi_point(app)
    # Register the hover helper before the chart injector: because Flask runs
    # after_request hooks in reverse registration order, the helper script ends
    # up after the main chart script in HTML and can safely enhance every redraw.
    install_online_offline_hover_fix(app)
    # Online/offline trend API uses the already-patched multi-point department
    # lookup and OLAP request helpers, so combined-point charts work too.
    install_online_offline_trends(app)
    # Closed points can disappear from the current iikoCloud inventory API even
    # though their historical sales remain available in iikoServer OLAP.
    install_archived_points(app)
    install_speed_patch(app)
    install_chart_hover(app)
    install_preset_controls(app)
    # Telegram webhook is installed last so report commands use all active analytics patches.
    install_telegram_bot(app)
    install_procurement_diagnostics(app)
    install_staff_diagnostics(app)
    install_staff_analytics(app)

    app._analytics_runtime_installed = True
