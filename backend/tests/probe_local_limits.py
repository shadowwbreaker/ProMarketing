"""Bounded HTTP probe for an isolated local test stack, never public hosting."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import httpx


def main():
    target = "http://127.0.0.1:8000/api/v1/catalog/accounts?limit=1"
    with httpx.Client(timeout=30, trust_env=False, limits=httpx.Limits(max_connections=8)) as client:
        def request(_):
            try:
                response = client.get(target)
                return response.status_code, response.headers.get("Retry-After")
            except httpx.HTTPError:
                return "network_error", None

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(request, range(340)))
    counts = Counter(code for code, _ in results)
    print(dict(counts))
    assert counts == {200: 300, 429: 40}, counts
    assert all(wait and int(wait) > 0 for code, wait in results if code == 429)
    print("Atomic Redis HTTP limit: 300 accepted, 40 throttled, no 5xx.")


if __name__ == "__main__":
    main()
