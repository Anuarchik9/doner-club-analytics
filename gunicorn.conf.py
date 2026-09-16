def post_worker_init(worker):
    from dashboard_auth import install_auth

    install_auth(worker.wsgi)
