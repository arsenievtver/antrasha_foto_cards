#!/usr/bin/env python3
"""Сгенерировать пару VAPID-ключей для Web Push.

Запуск (macOS — команды `python` часто нет, используйте python3 или venv):

  cd backend && python3 scripts/generate_vapid_keys.py

Или из корня репозитория (создаст/обновит backend/.venv при необходимости):

  bash scripts/generate-vapid-keys.sh
"""

from __future__ import annotations

import base64

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def main() -> None:
    key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    private_numbers = key.private_numbers().private_value.to_bytes(32, "big")
    public_key = key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    print("# Добавьте в backend/.env или корневой .env:")
    print(f"VAPID_PUBLIC_KEY={_b64url(public_key)}")
    print(f"VAPID_PRIVATE_KEY={_b64url(private_numbers)}")
    print('VAPID_CLAIMS_SUB=mailto:notify@antrasha.ru')


if __name__ == "__main__":
    main()
