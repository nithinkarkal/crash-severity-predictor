#!/usr/bin/env python3
"""
Generate the secrets you paste into the Hugging Face Space
(Settings -> Variables and secrets).

Backend passwords are stored as base64-encoded bcrypt hashes (matches
services/backend/src/config/settings.py). This prints ready-to-paste values.

Usage:
    python deploy/hf-space/gen_secrets.py                 # uses defaults below
    python deploy/hf-space/gen_secrets.py --demo-pass s3cret --admin-pass Adm!n42
"""

from __future__ import annotations

import argparse
import base64
import secrets

import bcrypt


def b64_bcrypt(password: str) -> str:
    return base64.b64encode(bcrypt.hashpw(password.encode(), bcrypt.gensalt())).decode()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--demo-user", default="demo")
    p.add_argument("--demo-pass", default="demo1234")
    p.add_argument("--admin-user", default="admin")
    p.add_argument("--admin-pass", default=secrets.token_urlsafe(12))
    args = p.parse_args()

    jwt_secret = secrets.token_urlsafe(48)

    print("\n=== HF Space -> Settings -> Variables and secrets ===\n")
    print("# --- SECRETS (mask these) ---")
    print(f"JWT_SECRET_KEY={jwt_secret}")
    print("DAGSHUB_USER_TOKEN=<paste your NEW rotated DagsHub token>")
    print(f"USER_USERNAME={args.demo_user}")
    print(f"USER_PASSWORD_HASH_B64={b64_bcrypt(args.demo_pass)}")
    print(f"ADMIN_USERNAME={args.admin_user}")
    print(f"ADMIN_PASSWORD_HASH_B64={b64_bcrypt(args.admin_pass)}")
    print()
    print("# --- VARIABLES (plain) ---")
    print("DAGSHUB_REPO_OWNER=nithinkarkal")
    print("DAGSHUB_REPO_NAME=crash-severity-predictor")
    print("CLOUD_DEMO=1")
    print(f"DEMO_USERNAME={args.demo_user}")
    print(f"DEMO_PASSWORD={args.demo_pass}")
    print()
    print("# (BACKEND_URL is already set inside the Dockerfile.)")
    print(f"\n# Admin password (store somewhere safe, NOT public): {args.admin_pass}\n")


if __name__ == "__main__":
    main()
