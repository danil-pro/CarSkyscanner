from scrapers.base import BaseScraper, ScrapeResult


class FacebookScraper(BaseScraper):
    """Stub: FB Marketplace requires an authenticated session (out of MVP scope)."""

    source = "facebook"

    def build_url(self) -> str:
        return "https://www.facebook.com/marketplace/"

    async def parse_page(self, page):  # never reached
        return []

    async def run(self, playwright=None) -> ScrapeResult:
        return ScrapeResult(source=self.source, blocked=True, reason="login required (stub)")
