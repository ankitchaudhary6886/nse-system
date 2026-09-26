"""Chartink adapter for user-supplied screener URLs."""

import re

import requests

from data_sources.core import BaseSourceAdapter, SourceRegistry


class ChartinkSymbolsAdapter(BaseSourceAdapter):
    name = "chartink"
    datasets = ("universe.chartink_symbols",)

    def fetch(self, url):
        def request():
            response = requests.get(
                url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
            response.raise_for_status()
            return sorted(set(re.findall(
                r"/stocks/NSE/([A-Z0-9]+)", response.text)))

        return self._execute(request)


def register_adapters(registry: SourceRegistry):
    registry.register(ChartinkSymbolsAdapter())
