import os

# The dashboard makes several independent iiko/iikoCloud requests in parallel.
# gthread lets one Render instance process those network-bound requests concurrently
# instead of queueing them one-by-one behind a single synchronous worker.
worker_class = "gthread"
workers = 1
threads = 8
timeout = 120
keepalive = 5


def post_worker_init(worker):
    from runtime import install_runtime
    install_runtime(worker.wsgi)
