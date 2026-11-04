"""Configure the one-time Elshamii developer activation code.
Run by the developer before packaging; the code itself is never written to disk.
"""
from __future__ import annotations
import getpass
import hashlib
import secrets
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent / ".env"

def main() -> None:
    code = getpass.getpass("Developer activation code: ")
    confirm = getpass.getpass("Confirm activation code: ")
    if not code or code != confirm:
        raise SystemExit("Codes did not match or were empty.")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", code.encode("utf-8"), salt.encode("utf-8"), 310000).hex()
    value = f"{salt}${digest}"
    if not ENV_FILE.exists():
        example = ENV_FILE.with_name(".env.example")
        if example.exists():
            ENV_FILE.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    lines = [line for line in lines if not line.startswith("ELSHAMII_DEVELOPER_CODE_HASH=")]
    lines.append(f"ELSHAMII_DEVELOPER_CODE_HASH={value}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Developer activation hash saved to backend/.env. Keep this file private.")

if __name__ == "__main__":
    main()
