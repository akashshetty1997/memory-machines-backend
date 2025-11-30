"""
Load Test Script - Memory Machines Backend
Sends 1000 RPM mixed JSON/TXT requests to /ingest
"""

import argparse
import random
import string
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4

import requests


def random_text(length):
    """Generate random text of given length."""
    return "".join(random.choices(string.ascii_letters + string.digits + " ", k=length))


def send_json_request(url, tenant_id):
    """Send a JSON request to /ingest."""
    start = time.time()
    payload = {
        "tenant_id": tenant_id,
        "log_id": str(uuid4()),
        "text": random_text(random.randint(50, 500)),
    }
    try:
        r = requests.post(f"{url}/ingest", json=payload, timeout=10)
        return r.status_code, time.time() - start
    except Exception:
        return 0, time.time() - start


def send_text_request(url, tenant_id):
    """Send a text/plain request to /ingest."""
    start = time.time()
    headers = {"Content-Type": "text/plain", "X-Tenant-ID": tenant_id}
    body = random_text(random.randint(50, 500))
    try:
        r = requests.post(f"{url}/ingest", data=body, headers=headers, timeout=10)
        return r.status_code, time.time() - start
    except Exception:
        return 0, time.time() - start


def main():
    parser = argparse.ArgumentParser(description="Load test /ingest endpoint")
    parser.add_argument("url", help="Base URL (e.g., https://ingestion-xxx.run.app)")
    parser.add_argument("--rpm", type=int, default=1000, help="Requests per minute")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds")
    args = parser.parse_args()

    tenants = ["acme_corp", "beta_inc", "gamma_llc"]
    total_requests = int(args.rpm * args.duration / 60)
    delay = 60 / args.rpm

    print(f"Target: {args.rpm} RPM for {args.duration}s = {total_requests} requests")
    print(f"URL: {args.url}")
    print()

    results = {"202": 0, "4xx": 0, "5xx": 0, "timeout": 0}
    latencies = []

    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = []
        start_time = time.time()

        for i in range(total_requests):
            tenant = random.choice(tenants)
            if random.random() < 0.5:
                futures.append(executor.submit(send_json_request, args.url, tenant))
            else:
                futures.append(executor.submit(send_text_request, args.url, tenant))

            # Pace requests
            elapsed = time.time() - start_time
            expected = (i + 1) * delay
            if expected > elapsed:
                time.sleep(expected - elapsed)

        # Collect results
        for f in as_completed(futures):
            code, latency = f.result()
            latencies.append(latency)
            if code == 202:
                results["202"] += 1
            elif code == 0:
                results["timeout"] += 1
            elif 400 <= code < 500:
                results["4xx"] += 1
            else:
                results["5xx"] += 1

    # Report
    print("=== Results ===")
    print(f"202 Accepted: {results['202']}")
    print(f"4xx errors:   {results['4xx']}")
    print(f"5xx errors:   {results['5xx']}")
    print(f"Timeouts:     {results['timeout']}")
    print()
    print(f"Avg latency:  {sum(latencies)/len(latencies)*1000:.1f}ms")
    print(f"p50 latency:  {sorted(latencies)[len(latencies)//2]*1000:.1f}ms")
    print(f"p99 latency:  {sorted(latencies)[int(len(latencies)*0.99)]*1000:.1f}ms")

    success_rate = results["202"] / total_requests * 100
    print(f"\nSuccess rate: {success_rate:.1f}%")
    if success_rate >= 99:
        print("✓ PASS: Flood test passed")
    else:
        print("✗ FAIL: Too many non-202 responses")


if __name__ == "__main__":
    main()
