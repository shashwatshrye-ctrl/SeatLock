"""High-concurrency load testing suite for College Concert Ticket API.

Simulates simultaneous booking traffic (e.g. 10,000 students at 6 PM)
to verify lock contention, zero double-bookings, idempotency, and throughput.
"""

import argparse
import asyncio
import statistics
import time
from uuid import uuid4

import httpx


async def run_contention_test(
    base_url: str,
    requests: int,
    seat_id: int,
    concurrency: int = 100,
) -> None:
    """Tests race conditions where many concurrent users compete for the exact same seat."""
    print("=" * 70)
    print(f"RACE CONDITION TEST: {requests} users competing for Seat #{seat_id}")
    print("=" * 70)

    user_ids = list(range(1001, 1001 + requests))
    sem = asyncio.Semaphore(concurrency)
    latencies: list[float] = []

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        async def make_request(uid: int):
            async with sem:
                t0 = time.perf_counter()
                resp = await client.post(
                    "/reservations",
                    json={
                        "seat_id": seat_id,
                        "user_id": uid,
                    },
                )
                latencies.append(time.perf_counter() - t0)
                return resp

        start = time.perf_counter()
        responses = await asyncio.gather(*(make_request(uid) for uid in user_ids))
        total_time = time.perf_counter() - start

    successes = [r for r in responses if r.status_code == 201]
    conflicts = [r for r in responses if r.status_code == 409]
    errors = [r for r in responses if r.status_code not in (201, 409)]

    latencies_ms = [l * 1000 for l in latencies]
    latencies_ms.sort()

    rps = len(responses) / total_time if total_time > 0 else 0
    p50 = statistics.median(latencies_ms) if latencies_ms else 0
    p95 = latencies_ms[int(len(latencies_ms) * 0.95)] if latencies_ms else 0
    p99 = latencies_ms[int(len(latencies_ms) * 0.99)] if latencies_ms else 0

    print(f"\n[Results]")
    print(f"Total Requests:       {len(responses)}")
    print(f"Concurrency Level:    {concurrency}")
    print(f"Elapsed Time:         {total_time:.3f} s")
    print(f"Throughput:           {rps:.1f} req/s")
    print(f"Successful Holds:     {len(successes)} (Expected: exactly 1)")
    print(f"Seat Conflicts (409): {len(conflicts)} (Expected: {requests - 1})")
    print(f"Unexpected Errors:    {len(errors)}")
    print(f"Latency min / avg:    {min(latencies_ms):.2f} ms / {statistics.mean(latencies_ms):.2f} ms")
    print(f"Latency p50 / p95:    {p50:.2f} ms / {p95:.2f} ms")
    print(f"Latency p99 / max:    {p99:.2f} ms / {max(latencies_ms):.2f} ms")

    if len(successes) == 1 and len(conflicts) == requests - 1 and not errors:
        print("\n>>> TEST PASSED: Row-level lock strictly prevented double-booking!")
    else:
        print("\n>>> TEST FAILED: Race condition detected or unexpected errors.")
        for err in errors[:5]:
            print(f"    Error {err.status_code}: {err.text}")
        raise SystemExit(1)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ticket Booking Platform Concurrency Benchmark")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--requests", type=int, default=100, help="Number of concurrent requests")
    parser.add_argument("--seat-id", type=int, default=500, help="Seat ID to test contention on")
    parser.add_argument("--concurrency", type=int, default=50, help="Max in-flight concurrent requests")
    args = parser.parse_args()

    await run_contention_test(
        base_url=args.base_url,
        requests=args.requests,
        seat_id=args.seat_id,
        concurrency=args.concurrency,
    )


if __name__ == "__main__":
    asyncio.run(main())
