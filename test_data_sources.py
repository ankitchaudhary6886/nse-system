import unittest

from data_sources.core import (
    BaseSourceAdapter,
    ProviderFetchError,
    SourceRegistry,
)


class _FakeAdapter(BaseSourceAdapter):
    datasets = ("test.value",)

    def __init__(self, name, result=None, error=None, max_calls=60):
        self.name = name
        self.result = result
        self.error = error
        super().__init__(max_calls=max_calls, window_seconds=60)

    def fetch(self):
        def run():
            if self.error:
                raise self.error
            return self.result
        return self._execute(run)


class SourceRegistryTests(unittest.TestCase):
    def test_falls_back_after_provider_error_and_reports_health(self):
        registry = SourceRegistry()
        registry.register(_FakeAdapter("first", error=OSError("offline")))
        registry.register(_FakeAdapter("second", result=["accepted"]))

        result = registry.fetch(
            "test.value", ("first", "second"),
            accept=lambda value: bool(value))

        self.assertEqual(result.data, ["accepted"])
        self.assertEqual(result.provider, "second")
        health = {item["provider"]: item for item in registry.health()}
        self.assertEqual(health["first"]["state"], "unavailable")
        self.assertEqual(health["first"]["failures"], 1)
        self.assertEqual(health["second"]["state"], "healthy")

    def test_rejected_results_do_not_masquerade_as_success(self):
        registry = SourceRegistry()
        registry.register(_FakeAdapter("empty", result=[]))

        with self.assertRaises(ProviderFetchError) as error:
            registry.fetch(
                "test.value", ("empty",), accept=lambda value: bool(value))

        self.assertEqual(error.exception.errors["empty"],
                         "provider result rejected")

    def test_exhausted_fallback_raises_explicit_error(self):
        registry = SourceRegistry()
        registry.register(_FakeAdapter("broken", error=OSError("offline")))

        with self.assertRaises(ProviderFetchError) as error:
            registry.fetch("test.value", ("broken",))

        self.assertIn("offline", str(error.exception))

    def test_builtins_are_discoverable_without_network_calls(self):
        registry = SourceRegistry()
        sources = {item["provider"]: item for item in registry.health()}

        self.assertTrue({
            "tradingview",
            "yahoo_finance",
            "nse_constituents_local_csv",
            "nse_constituents_api",
            "nse_constituents_archive_csv",
            "chartink",
        }.issubset(sources))
        self.assertEqual(sources["tradingview"]["state"], "not_checked")


if __name__ == "__main__":
    unittest.main()
