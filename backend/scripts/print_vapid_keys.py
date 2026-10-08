#!/usr/bin/env python3
"""Generate VAPID key material for web push (run on the server; do not commit output)."""

from __future__ import annotations

import base64

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid


def main() -> None:
    v = Vapid()
    v.generate_keys()
    raw_pub = v.public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    public_b64 = base64.urlsafe_b64encode(raw_pub).decode().rstrip("=")
    private_pem = v.private_pem().decode()
    public_pem = v.public_pem().decode()

    print("# Add to repo-root .env.staging (frontend build arg):")
    print(f"NEXT_PUBLIC_WEB_PUSH_VAPID_PUBLIC_KEY={public_b64}")
    print()
    print("# Add to backend/.env.staging:")
    print("WEB_PUSH_VAPID_SUBJECT=mailto:notifications@flintapply.com")
    print(f"WEB_PUSH_VAPID_PUBLIC_KEY={public_pem.replace(chr(10), '\\\\n')}")
    print(f"WEB_PUSH_VAPID_PRIVATE_KEY={private_pem.replace(chr(10), '\\\\n')}")


if __name__ == "__main__":
    main()
