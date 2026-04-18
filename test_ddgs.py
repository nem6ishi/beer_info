from backend.src.services.untappd.searcher import get_untappd_url
import logging
logging.basicConfig(level=logging.DEBUG)

res = get_untappd_url(brewery_name="Inkhorn Brewing", beer_name="Uguisu")
print(res)
