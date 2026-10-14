"""Concurrent smoke test against a running API and Supabase project."""

import argparse
import asyncio
import time
from uuid import uuid4

import httpx


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--seat-id", type=int, default=500)
    args = parser.parse_args()

    user_ids = [str(uuid4()) for _ in range(args.requests)]
    start = time.perf_counter()

    async with httpx.AsyncClient(base_url=args.base_url, timeout=30) as client:
        responses = await asyncio.gather(
            *(
                client.post(
                    "/reservations",
                    json={
                        "user_id": user_id,
                        "seat_id": args.seat_id,
                        "idempotency_key": f"load-{uuid4()}",
                    },
                )
                for user_id in user_ids
            )
        )

    elapsed = time.perf_counter() - start
    successes = sum(response.status_code == 201 for response in responses)
    conflicts = sum(response.status_code == 409 for response in responses)
    errors = [
        (response.status_code, response.text)
        for response in responses
        if response.status_code not in (201, 409)
    ]
    print(
        f"requests={len(responses)} success={successes} "
        f"conflict={conflicts} unexpected={len(errors)} elapsed_seconds={elapsed:.3f}"
    )
    if (
        successes != 1
        or conflicts != len(responses) - 1
        or errors
    ):
        for error in errors[:10]:
            print(f"unexpected_response={error}")
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
