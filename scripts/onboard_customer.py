import argparse
import os
import sys
from typing import Any

import requests


def request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.request(method, url, json=payload, timeout=20)
    if response.status_code >= 400:
        raise RuntimeError(f"{response.status_code}: {response.text}")
    if response.status_code == 204:
        return {}
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Onboard a customer into Quilr by calling the portal API."
    )
    parser.add_argument("--api-base", default=os.environ.get("API_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--customer-name", required=True)
    parser.add_argument("--contact-email", default="")
    parser.add_argument("--instance-id", default="")
    parser.add_argument("--instance-name", default="")
    parser.add_argument("--instance-bff-url", default="")
    parser.add_argument("--instance-status", default="active")
    parser.add_argument("--pg-host", default="")
    parser.add_argument("--pg-port", default="")
    parser.add_argument("--pg-user", default="")
    parser.add_argument("--pg-password", default="")
    parser.add_argument("--neo4j-host", default="")
    parser.add_argument("--neo4j-port", default="")
    parser.add_argument("--neo4j-user", default="")
    parser.add_argument("--neo4j-password", default="")
    parser.add_argument("--list-instances", action="store_true")

    args = parser.parse_args()

    if args.list_instances:
        instances = request_json("GET", f"{args.api_base}/api/instances")
        print("Instances:")
        for instance in instances:
            print(f"- {instance['id']} | {instance['name']} | {instance.get('bff_url') or 'n/a'}")
        return 0

    customer_payload = {
        "name": args.customer_name,
        "contact_email": args.contact_email or None,
        "instance_id": args.instance_id or None,
    }

    if args.instance_name:
        payload = {
            "instance": {
                "name": args.instance_name,
                "bff_url": args.instance_bff_url or None,
                "status": args.instance_status or "active",
                "pg_host": args.pg_host or None,
                "pg_port": args.pg_port or None,
                "pg_user": args.pg_user or None,
                "pg_password": args.pg_password or None,
                "neo4j_host": args.neo4j_host or None,
                "neo4j_port": args.neo4j_port or None,
                "neo4j_user": args.neo4j_user or None,
                "neo4j_password": args.neo4j_password or None,
            },
            "customer": customer_payload,
        }
        response = request_json("POST", f"{args.api_base}/api/onboard", payload)
        print("Onboarded customer via new instance.")
        print(response)
        return 0

    if not args.instance_id:
        print("Either --instance-id or --instance-name is required.")
        return 1

    response = request_json("POST", f"{args.api_base}/api/customers", customer_payload)
    print("Customer created.")
    print(response)
    return 0


if __name__ == "__main__":
    sys.exit(main())
