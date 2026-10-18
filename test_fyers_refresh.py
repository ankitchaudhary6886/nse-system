"""Offline tests for the pin-based Fyers token renewal + UI exchange helper."""
import json
import os
import unittest
from pathlib import Path
from unittest import mock

import fyers_client as fc

from test_fyers_integration import FakeResponse, FakeSession


def make_client(handler, token=""):
    return fc.FyersClient(app_id="APP-100", access_token=token,
                          session=FakeSession(handler))


class RefreshTokenTests(unittest.TestCase):
    def _store(self, name):
        path = Path("data") / f"test_token_refresh_{name}.json"
        self.addCleanup(lambda: path.unlink() if path.exists() else None)
        store = fc.TokenStore(path)
        store.save("old-token", "refresh-abc")
        return store

    def test_refresh_posts_documented_body_and_saves_new_token(self):
        store = self._store("ok")

        def handler(method, url, params):
            if "validate-refresh-token" in url:
                return {"s": "ok", "access_token": "new-token",
                        "refresh_token": "refresh-next"}
            raise AssertionError(url)

        client = make_client(handler)
        client.token_store = store
        client.token = "old-token"
        with mock.patch.dict(os.environ, {"FYERS_PIN": "1234",
                                          "FYERS_SECRET_ID": "sec"}):
            result = client.refresh_access_token()
        self.assertTrue(result["ok"])
        call = client._session.calls[0]
        body = call[2]
        self.assertEqual(body["grant_type"], "refresh_token")
        self.assertEqual(body["refresh_token"], "refresh-abc")
        self.assertEqual(body["pin"], "1234")
        self.assertEqual(body["appIdHash"], fc.app_id_hash("APP-100", "sec"))
        self.assertEqual(store.access_token(), "new-token")
        self.assertEqual(store.load()["refresh_token"], "refresh-next")

    def test_refresh_without_pin_is_clear_error(self):
        store = self._store("nopin")
        client = make_client(lambda *a: {}, token="old")
        client.token_store = store
        with mock.patch.dict(os.environ, {"FYERS_PIN": ""}):
            with self.assertRaises(fc.FyersAuthError) as ctx:
                client.refresh_access_token()
        self.assertIn("FYERS_PIN", str(ctx.exception))

    def test_refresh_without_refresh_token_is_clear_error(self):
        path = Path("data") / "test_token_refresh_empty.json"
        self.addCleanup(lambda: path.unlink() if path.exists() else None)
        store = fc.TokenStore(path)
        fc.TokenStore(path).save("only-access", "")
        client = make_client(lambda *a: {}, token="only-access")
        client.token_store = store
        with mock.patch.dict(os.environ, {"FYERS_PIN": "1234"}):
            with self.assertRaises(fc.FyersAuthError) as ctx:
                client.refresh_access_token()
        self.assertIn("refresh_token", str(ctx.exception))

    def test_token_status_exposes_refresh_presence(self):
        store = self._store("status")
        self.assertTrue(store.status()["refresh_present"])


class ExchangeHelperTests(unittest.TestCase):
    def test_exchange_returns_no_token_and_saves_it(self):
        path = Path("data") / "test_token_exchange_helper.json"
        self.addCleanup(lambda: path.unlink() if path.exists() else None)
        store = fc.TokenStore(path)

        def handler(method, url, payload):
            if "/validate-authcode" in url:
                return {"s": "ok", "access_token": "tok-1",
                        "refresh_token": "ref-1"}
            if url.endswith("/profile"):
                return {"s": "ok", "data": {"display_name": "Tester"}}
            raise AssertionError(url)

        client = make_client(handler)
        with mock.patch.dict(os.environ, {"FYERS_APP_ID": "APP-100",
                                          "FYERS_SECRET_ID": "sec"}):
            result = fc.exchange_code("my-code", store=store, client=client)
        self.assertTrue(result["ok"])
        self.assertEqual(result["profile"], "Tester")
        self.assertNotIn("access_token", json.dumps(result))
        self.assertEqual(store.access_token(), "tok-1")

    def test_exchange_error_is_returned_not_raised(self):
        def handler(method, url, payload):
            return FakeResponse({"s": "error", "code": -437,
                                 "message": "invalid auth code"},
                                status_code=400)

        client = make_client(handler)
        with mock.patch.dict(os.environ, {"FYERS_APP_ID": "APP-100",
                                          "FYERS_SECRET_ID": "sec"}):
            result = fc.exchange_code("bad", client=client)
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], -437)


if __name__ == "__main__":
    unittest.main(verbosity=2)
