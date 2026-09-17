#!/usr/bin/env python3
"""
Generate a new self-signed wildcard cert/key pair and drop it into
data/certs_incoming/, exactly the way an admin would after obtaining a real
renewed certificate from a CA. This is the trigger for the automatic
renewal half of the demo — run it, then watch the dashboard (or the
container logs) as the watcher picks it up within a second or two.

Examples
--------
Renew one of the seeded demo certs (see scripts/seed_demo.py for the list):

    python scripts/generate_sample_cert.py --device-type F5 --device-name f5-dc2-dr-lb01 --domain "*.corp.example.com"

Demonstrate the failure path (mock device always rejects "fail-demo" domains):

    python scripts/generate_sample_cert.py --device-type F5 --device-name f5-fail-demo-lb01 --domain "*.fail-demo.example.com"
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.cert_utils import generate_self_signed_wildcard, write_pem_pair  # noqa: E402
from app.config import settings  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--device-type", required=True, choices=["F5", "ISE"])
    parser.add_argument("--device-name", required=True, help="e.g. f5-dc1-prod-lb01")
    parser.add_argument("--domain", required=True, help='e.g. "*.example.com" (must match an existing record)')
    parser.add_argument("--valid-days", type=int, default=365)
    args = parser.parse_args()

    cert_pem, key_pem = generate_self_signed_wildcard(args.domain, valid_days=args.valid_days)
    stem = f"{args.device_type}_{args.device_name}"
    cert_path = write_pem_pair(settings.incoming_dir, stem, cert_pem, key_pem)

    print(f"已產生新憑證並放置於固定資料夾：{cert_path}")
    print(f"（有效期限：{args.valid_days} 天，網域：{args.domain}）")
    print("若 app 服務正在執行，資料夾監控將於數秒內自動偵測並完成更換。")


if __name__ == "__main__":
    main()
