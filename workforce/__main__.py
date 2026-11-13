"""Local operator CLI. Do not expose this as a remote/public API."""
import argparse
import json
from pathlib import Path

from .runtime import Workforce, load_profiles


def main():
    parser = argparse.ArgumentParser(description="JCi workforce offline staging CLI")
    parser.add_argument("--db", default=".local/workforce.sqlite")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("profiles")
    sub.add_parser("metrics")
    demo = sub.add_parser("demo")
    demo.add_argument("--country", choices=["US", "AE"], default="US")
    live = sub.add_parser("live-test", help="Small synthetic OpenAI smoke test")
    live.add_argument("--credential-proxy", action="store_true", required=True)
    live.add_argument("--model", default="gpt-5.4-mini-2026-03-17")
    live.add_argument("--role", choices=sorted(load_profiles()), default="ai-customer-support")
    live.add_argument("--country", choices=["US", "AE"], default="US")
    live.add_argument("--case-id", required=True, help="Stable idempotency key for this test")
    live.add_argument("--max-calls", type=int, default=3)
    args = parser.parse_args()
    if args.command == "profiles":
        print(json.dumps(list(load_profiles().values()), indent=2))
        return
    provider = None
    if args.command == "live-test":
        from .openai_provider import OpenAIProvider
        provider = OpenAIProvider(
            credential_proxy=args.credential_proxy, model=args.model, max_calls=args.max_calls,
        )
    worker = Workforce(Path(args.db), provider=provider)
    try:
        if args.command == "demo":
            for role in worker.profiles:
                task_id = worker.submit(role, {
                    "brief": "Prepare an internal role-readiness draft; do not contact anyone.",
                    "source_ids": ["internal:role-readiness-brief"], "country": args.country,
                }, idempotency_key=f"readiness:{args.country}:{role}")
                task = worker.run(task_id)
                print(f'{role}: {task["status"]}')
        if args.command == "live-test":
            task_id = worker.submit(args.role, {
                "brief": (
                    "SYNTHETIC TEST ONLY. A fictional customer asks whether JCi has verified "
                    "listings or a live secure portal. Supplied facts: this is a preview, "
                    "there is no verified inventory supplied, and production login is not "
                    "connected. Draft a truthful internal reply of at most 100 words. "
                    "Return one draft_note action only. Do not send anything. "
                    "Do not claim anyone will contact the customer."
                ),
                "source_ids": ["internal:synthetic-preview-facts"],
                "country": args.country,
            }, idempotency_key="openai-test:" + args.case_id)
            task = worker.run(task_id)
            print(json.dumps({
                "task_id": task_id, "status": task["status"], "error_code": task["error_code"],
                "output": json.loads(task["output_json"]) if task["output_json"] else None,
                "approval_count": len(task["approvals"]),
            }, indent=2))
            if task["status"] != "completed":
                raise SystemExit(1)
        print(json.dumps(worker.metrics(), indent=2))
    finally:
        worker.close()


if __name__ == "__main__":
    main()
