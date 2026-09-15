"""Runtime hardening for Doner Club Analytics.

Python imports sitecustomize automatically on startup. We use it to make the
nomenclature lookup resilient without changing the analytics contract.
"""

import time

try:
    import app as analytics_app

    # Product names/articles change rarely; keeping the successful map longer
    # avoids repeated large nomenclature calls on Render cold starts/long reports.
    analytics_app.PRODUCTS_TTL_SECONDS = 6 * 60 * 60

    _original_get_products_map = analytics_app.get_products_map

    def robust_get_products_map(force_refresh=False):
        last_error = None

        # Retry transient iikoCloud / rate-limit / network failures. A failed
        # nomenclature request used to make the dashboard fall back to UUIDs.
        for attempt, delay in enumerate((0, 1, 3), start=1):
            if delay:
                time.sleep(delay)
            try:
                products = _original_get_products_map(
                    force_refresh=force_refresh or attempt > 1
                )
                if products:
                    return products
            except Exception as error:
                last_error = error

        # If a previously successful map exists, prefer stale human-readable
        # names over exposing internal product UUIDs.
        stale = analytics_app._products_cache.get("value")
        if stale:
            return stale

        if last_error:
            raise last_error
        raise RuntimeError("iiko nomenclature returned no products")

    analytics_app.get_products_map = robust_get_products_map
except Exception:
    # Never prevent the web service itself from starting because of optional
    # startup hardening.
    pass
