import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def download(url: str) -> bytes:
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    with requests.Session() as session:
        session.mount("https://", HTTPAdapter(max_retries=retry))
        response = session.get(url, timeout=(10, 60), headers={"User-Agent": "BrownstoneMarkets/0.1"})
        response.raise_for_status()
        if not response.content or len(response.content) > 100_000_000:
            raise ValueError("Empty or oversized source CSV")
        return response.content
