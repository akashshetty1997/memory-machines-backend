# load_test.py
import argparse
import asyncio
import time
from collections import Counter

import aiohttp

DEFAULT_URL = "https://ingestion-555551574544.us-central1.run.app/ingest"


async def send_request(session: aiohttp.ClientSession, url: str, i: int):
    """
    Send a single ingestion request and return (status, latency_seconds).
    """
    payload = {
        "tenant_id": "loadtest",
        "log_id": f"lt-{i}",
        "text": f"test-{i}",
    }

    start = time.time()
    try:
        async with session.post(url, json=payload) as resp:
            status = resp.status
    except Exception:
        status = None
    latency = time.time() - start
    return status, latency


async def run_load_test(url: str, rpm: int, duration: int, concurrency: int):
    """
    Run a load test against the ingestion endpoint.

    - url: ingestion URL (/ingest)
    - rpm: target requests per minute
    - duration: duration in seconds
    - concurrency: max concurrent in-flight requests
    """
    if rpm <= 0 or duration <= 0:
        raise ValueError("rpm and duration must be positive integers")

    total_requests = int(rpm * duration / 60)
    if total_requests == 0:
        total_requests = 1

    interval = 60.0 / rpm  # seconds between request starts
    semaphore = asyncio.Semaphore(concurrency)

    print(
        f"Target: {total_requests} requests over {duration}s "
        f"({rpm} req/min, concurrency={concurrency})"
    )

    async with aiohttp.ClientSession() as session:
        tasks = []

        async def worker(i: int):
            async with semaphore:
                return await send_request(session, url, i)

        start = time.time()
        for i in range(total_requests):
            tasks.append(asyncio.create_task(worker(i)))
            await asyncio.sleep(interval)

        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start

    statuses = [s for (s, _) in results]
    latencies = [lat for (s, lat) in results if s == 202]

    counts = Counter(statuses)
    success_202 = counts.get(202, 0)
    total = len(statuses)

    print("\n=== Results ===")
    print(f"Total requests: {total}")
    print(f"202 Accepted : {success_202}")
    for code, count in sorted(counts.items()):
        if code is None:
            print(f"Errors (exceptions): {count}")
        elif code != 202:
            print(f"{code} responses: {count}")

    print(f"\nTotal time: {elapsed:.2f}s")
    print(f"Effective rate: {total / elapsed:.1f} req/sec")

    if latencies:
        latencies_sorted = sorted(latencies)
        p50 = latencies_sorted[int(0.50 * len(latencies_sorted))]
        p95 = latencies_sorted[int(0.95 * len(latencies_sorted))]
        p99 = latencies_sorted[int(0.99 * len(latencies_sorted))]

        print("\nLatency (for 202 responses):")
        print(f"  avg : {sum(latencies) / len(latencies):.3f}s")
        print(f"  p50 : {p50:.3f}s")
        print(f"  p95 : {p95:.3f}s")
        print(f"  p99 : {p99:.3f}s")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Simple load tester for Memory Machines ingestion service."
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=DEFAULT_URL,
        help=f"Ingestion URL (default: {DEFAULT_URL})",
    )
    parser.add_argument(
        "--rpm",
        type=int,
        default=1000,
        help="Target requests per minute (default: 1000)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Test duration in seconds (default: 60)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=100,
        help="Maximum number of concurrent requests (default: 100)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(
        run_load_test(
            url=args.url,
            rpm=args.rpm,
            duration=args.duration,
            concurrency=args.concurrency,
        )
    )
