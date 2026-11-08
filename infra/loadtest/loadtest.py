"""Simple HTTP load / flood test (no extra services needed).

Usage:
  python loadtest.py --base http://localhost:8000 --seconds 20 --concurrency 50            # throughput
  python loadtest.py --base http://localhost:8000 --seconds 15 --concurrency 200 --flood   # flood from one IP

Throughput mode walks what a visitor does (catalog, counts, home, an offer page).
Flood mode hammers one endpoint and, in parallel, measures how a *normal* request (health) is served —
the platform must keep answering while the attacker gets 429.
Only run against your own servers.
"""
import argparse
import asyncio
import statistics
import time
from collections import Counter

import httpx


async def worker(client, urls, stop, lat, codes):
    i = 0
    while time.monotonic() < stop:
        url = urls[i % len(urls)]
        i += 1
        t = time.monotonic()
        try:
            r = await client.get(url)
            codes[r.status_code] += 1
        except httpx.HTTPError as e:
            codes[type(e).__name__] += 1
            continue
        lat.append((time.monotonic() - t) * 1000)


async def probe(client, url, stop, lat):
    while time.monotonic() < stop:
        t = time.monotonic()
        try:
            await client.get(url)
            lat.append((time.monotonic() - t) * 1000)
        except httpx.HTTPError:
            lat.append(10_000)
        await asyncio.sleep(0.5)


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * p))] if xs else float("nan")


async def main(a):
    limits = httpx.Limits(max_connections=a.concurrency, max_keepalive_connections=a.concurrency)
    async with httpx.AsyncClient(base_url=a.base, timeout=10, limits=limits) as c:
        first = (await c.get("/api/v1/catalog/accounts")).json()["results"]
        offer = f"/api/v1/catalog/accounts/{first[0]['id']}" if first else "/api/v1/catalog/accounts"
        urls = ["/api/v1/catalog/accounts", "/api/v1/catalog/counts", "/api/v1/catalog/home", offer,
                "/api/v1/catalog/accounts?platform=tiktok&sort=price_asc"]
        if a.flood:
            urls = ["/api/v1/catalog/accounts"]
        lat, codes, probe_lat = [], Counter(), []
        stop = time.monotonic() + a.seconds
        start = time.monotonic()
        async with httpx.AsyncClient(base_url=a.base, timeout=10) as p:
            await asyncio.gather(*[worker(c, urls, stop, lat, codes) for _ in range(a.concurrency)],
                                 probe(p, "/api/v1/health/live", stop, probe_lat))
        dur = time.monotonic() - start
        total = sum(codes.values())
        print(f"mode={'flood' if a.flood else 'throughput'} concurrency={a.concurrency} duration={dur:.1f}s")
        print(f"requests={total} rps={total / dur:.0f} codes={dict(codes)}")
        if lat:
            print(f"latency ms: p50={pct(lat, .5):.0f} p95={pct(lat, .95):.0f} p99={pct(lat, .99):.0f} mean={statistics.mean(lat):.0f}")
        print(f"health probe during test: n={len(probe_lat)} p50={pct(probe_lat, .5):.0f}ms max={max(probe_lat or [0]):.0f}ms")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--seconds", type=int, default=20)
    ap.add_argument("--concurrency", type=int, default=50)
    ap.add_argument("--flood", action="store_true")
    asyncio.run(main(ap.parse_args()))
