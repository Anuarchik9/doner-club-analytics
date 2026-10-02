import os
import unittest
from unittest.mock import Mock, patch

import requests

import app as core
import stop_loss as stop


def response(payload, status=200):
    result = Mock(status_code=status)
    result.json.return_value = payload
    if status >= 400:
        result.raise_for_status.side_effect = requests.HTTPError(response=result)
    return result


class StopLossTests(unittest.TestCase):
    def setUp(self):
        stop._stop_token_cache.update(value=None, expires_at=0, credentials=None)
        self.env = patch.dict(os.environ, {
            "IIKO_APP_ID": "app", "IIKO_CLIENT_SECRET": "secret",
            "IIKO_API_KEY": "inventory-key", "IIKO_STOP_API_KEY": "stop-key",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.network = patch("requests.sessions.Session.request", side_effect=AssertionError("Unexpected network"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def test_dedicated_token_isolated_and_reused_for_both_organizations(self):
        with patch.object(core, "iiko_post", side_effect=AssertionError("Inventory auth used")), \
                patch.object(stop.requests, "post", side_effect=[
                    response({"token": "stop-token"}),
                    response({"terminalGroupStopLists": [{"organizationId": "arai", "items": []}]}),
                    response({"terminalGroupStopLists": [{"organizationId": "republic", "items": []}]}),
                ]) as post:
            self.assertEqual(stop._current_stop_list("arai"), [])
            self.assertEqual(stop._current_stop_list("republic"), [])
        self.assertEqual(post.call_args_list[0].kwargs["json"]["apiKey"], "stop-key")
        for call, org in zip(post.call_args_list[1:], ("arai", "republic")):
            self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer stop-token")
            self.assertEqual(call.kwargs["json"], {"organizationIds": [org]})

    def test_legacy_auth_without_override(self):
        with patch.dict(os.environ, {"IIKO_STOP_API_KEY": ""}), \
                patch.object(core, "iiko_post", return_value=response({"terminalGroupStopLists": []})) as post:
            self.assertEqual(stop._current_stop_list("arai"), [])
        post.assert_called_once_with("/api/1/stop_lists", {"organizationIds": ["arai"]}, timeout=30)

    def test_expired_token_refreshed_once(self):
        with patch.object(stop.requests, "post", side_effect=[
            response({"token": "expired"}), response({}, 401),
            response({"token": "fresh"}), response({}, 401),
        ]) as post:
            with self.assertRaises(requests.HTTPError):
                stop._current_stop_list("republic")
        self.assertEqual(post.call_count, 4)
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer fresh")

    def test_denied_is_not_an_empty_stop_list(self):
        with patch.object(stop, "_stop_post", return_value=response({"error": "ORGANIZATION_DENIED"}, 400)) as post:
            with self.assertRaises(requests.HTTPError):
                stop._current_stop_list("republic")
        post.assert_called_once()

    def test_malformed_or_other_organization_rejected(self):
        for payload in ({}, {"terminalGroupStopLists": None}, {"terminalGroupStopLists": [
            {"organizationId": "arai", "items": []}
        ]}):
            with self.subTest(payload=payload), patch.object(stop, "_stop_post", return_value=response(payload)):
                with self.assertRaises(RuntimeError):
                    stop._current_stop_list("republic")

    def test_nested_items_keep_terminal_balance_and_time(self):
        payload = {"terminalGroupStopLists": [{"organizationId": "republic", "items": [
            {"terminalGroupId": "terminal", "items": [
                {"productId": "dish", "balance": 0, "dateAdd": "2026-10-01 19:25:23.791"},
                {"productId": "limited", "balance": 2},
            ]}
        ]}]}
        with patch.object(stop, "_stop_post", return_value=response(payload)):
            items = stop._current_stop_list("republic")
        self.assertEqual(items[0]["productId"], "dish")
        self.assertEqual(items[0]["terminalGroupId"], "terminal")
        self.assertEqual(items[0]["balance"], 0)
        self.assertTrue(items[0]["sourceTime"].startswith("2026-10-01T19:25:23"))
        self.assertEqual(items[1]["balance"], 2)


if __name__ == "__main__":
    unittest.main()
