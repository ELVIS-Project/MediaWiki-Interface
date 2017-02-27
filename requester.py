from collections import deque
from random import shuffle, randint
import time
import requests
from settings import CW_DOMAIN


class RippingError(Exception):
    pass


class ProxiedFuzzedRequester:
    """Makes requests using a list of proxies and fuzzing."""

    __RIPPING_TEXT__ = """You have reached this message because the site ripping ban script has been triggered. Site ripping is forbidden; repeated offenders will be banned indefinitely."""

    def __init__(self, proxy_list=None, fuzz_range=None):
        """Create a ProxiedFuzzedRequester

        Args:
            proxy_list: a simple list of proxiable hosts.
                ex: ['http://178.151.193.9:8080', 'http://178.151.193.9:8080']
            fuzz_range: an upper and lower bound for fuzzing
                ex: [2, 15], (5, 10)
        """
        self.fuzz_range = (3, 15) if fuzz_range is None else tuple(fuzz_range)
        self._proxy_list = [] if proxy_list is None else proxy_list
        self._ordered_proxies = deque(proxy_list)
        shuffle(self._ordered_proxies)

        self._last_get = 0  # time.time() of last GET request.
        self._next_get = 0  # only time.time() greater than this can make next request.

    def get(self, url, **kwargs):
        """Make a request using the next proxy and respecting the fuzzing time.

        Assumes relative URLS are relative to http://imslp.org
        """

        # Wait until we are allowed to make another request, if needed.
        wait_time = self._next_get - time.time()
        if wait_time > 0:
            time.sleep(wait_time)

        # If url is relative, assume it is on IMSLP
        if url.startswith("/"):
            url = CW_DOMAIN + url

        # Get another proxy
        proxy = self._get_next_proxy()

        # get the stuff using requests
        resp = requests.get(url, proxies=proxy, **kwargs)
        self._check_anti_ripping(resp)

        # set the fuzzing
        self._set_next_get()
        return resp

    def _set_next_get(self):
        """Set last_get to now and next_get to now + random fuzz time."""
        self._last_get = time.time()
        self._next_get = self._last_get + randint(*self.fuzz_range)

    def _get_next_proxy(self):
        """Get the next proxy. Refill and shuffle the deque if needed."""
        if not self._proxy_list:
            return {}
        if not self._ordered_proxies:
            self._ordered_proxies = deque(self._proxy_list)
            shuffle(self._ordered_proxies)
        return {'http': self._ordered_proxies.pop()}

    def _check_anti_ripping(self, resp):
        content_type = resp.headers.get("Content-Type")
        if 'text/html' in content_type and self.__RIPPING_TEXT__ in resp.text:
            with open('ripping_page.html', 'wb') as f:
                f.write(resp.content)
            raise RippingError("Ripping detected. Exiting.")
