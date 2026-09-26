"""NSE constituent-list adapters used by the existing universe fallback."""

from data_sources.core import BaseSourceAdapter, SourceRegistry


class LocalNseConstituentsAdapter(BaseSourceAdapter):
    name = "nse_constituents_local_csv"
    datasets = ("universe.nse_constituents",)

    def fetch(self):
        import universe
        return universe.from_csv(universe.LOCAL_CSV)


class NseApiConstituentsAdapter(BaseSourceAdapter):
    name = "nse_constituents_api"
    datasets = ("universe.nse_constituents",)

    def fetch(self):
        import universe
        return universe.from_api()


class NseArchiveConstituentsAdapter(BaseSourceAdapter):
    name = "nse_constituents_archive_csv"
    datasets = ("universe.nse_constituents",)

    def fetch(self):
        import universe
        return universe.from_csv(universe.CSV_URL)


def register_adapters(registry: SourceRegistry):
    registry.register(LocalNseConstituentsAdapter())
    registry.register(NseApiConstituentsAdapter())
    registry.register(NseArchiveConstituentsAdapter())
