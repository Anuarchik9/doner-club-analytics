def post_worker_init(worker):
    from dashboard_auth import install_auth
    from sales_channel import install_sales_channel

    install_auth(worker.wsgi)
    install_sales_channel(worker.wsgi)
