def post_worker_init(worker):
    from dashboard_auth import install_auth
    from sales_channel import install_sales_channel
    from team_meal import install_team_meal
    from chart_hover import install_chart_hover

    install_auth(worker.wsgi)
    install_sales_channel(worker.wsgi)
    install_team_meal(worker.wsgi)
    install_chart_hover(worker.wsgi)
