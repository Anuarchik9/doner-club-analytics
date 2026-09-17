"""Small explicit dashboard allowlist overlay.

Passwords are still verified directly against iikoServer by dashboard_auth.
This module only adds approved iiko logins to the dashboard allowlist.
"""

APPROVED_IIKO_USERS = {"nurtleu", "elmira"}


def install_auth_allowlist_patch():
    import dashboard_auth

    if getattr(dashboard_auth, "_doner_allowlist_patch_installed", False):
        return
    dashboard_auth._doner_allowlist_patch_installed = True

    original_allowed_user = dashboard_auth._allowed_user

    def _allowed_user(login):
        normalized = (login or "").strip().lower()
        if normalized in APPROVED_IIKO_USERS:
            return True
        return original_allowed_user(login)

    dashboard_auth._allowed_user = _allowed_user
