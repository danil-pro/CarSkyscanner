from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from playwright.async_api import Playwright

from scrapers.base import ScrapeResult
from scrapers.olx import OLXScraper
from scrapers.otomoto import OtomotoScraper
from scrapers.filters import build_olx_url, build_otomoto_url


@dataclass
class ProviderResult:
    source: str
    listings: list[dict] = field(default_factory=list)
    status: str = "ok"
    reason: Optional[str] = None
    found: int = 0


def _from_scrape(source: str, result: ScrapeResult) -> ProviderResult:
    return ProviderResult(
        source=source,
        listings=result.listings,
        status="blocked" if result.blocked else "ok",
        reason=result.reason,
        found=len(result.listings),
    )


class ListingProvider(ABC):
    source: str

    @abstractmethod
    async def search(self, playwright: Playwright) -> ProviderResult:
        ...


class OLXProvider(OLXScraper, ListingProvider):
    source = "olx"

    def __init__(self, filters):
        self.filters = filters

    def build_url(self) -> str:
        return build_olx_url(self.filters)

    async def search(self, playwright: Playwright) -> ProviderResult:
        return _from_scrape(self.source, await self.run(playwright))


class OtomotoProvider(OtomotoScraper, ListingProvider):
    source = "otomoto"

    def __init__(self, filters):
        self.filters = filters

    def build_url(self) -> str:
        return build_otomoto_url(self.filters)

    async def search(self, playwright: Playwright) -> ProviderResult:
        return _from_scrape(self.source, await self.run(playwright))
