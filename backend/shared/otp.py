"""
shared/otp.py
--------------
Wraps MSG91's OTP API for phone verification.
Docs: https://docs.msg91.com/reference/send-otp

Needs env vars in production:
  MSG91_AUTH_KEY   - from your MSG91 account dashboard
  MSG91_TEMPLATE_ID - the approved OTP SMS template id

MOCK MODE: if REACH_MOCK_EXTERNAL=1 or MSG91_AUTH_KEY isn't set, no real SMS
is sent -- the OTP is generated locally and printed to the console instead,
so local dev/testing doesn't need an MSG91 account.
"""

import os
import random
import requests

MOCK_EXTERNAL = os.environ.get("REACH_MOCK_EXTERNAL", "0") == "1"
MSG91_AUTH_KEY = os.environ.get("MSG91_AUTH_KEY")
MSG91_TEMPLATE_ID = os.environ.get("MSG91_TEMPLATE_ID")

MSG91_SEND_URL = "https://control.msg91.com/api/v5/otp"
MSG91_VERIFY_URL = "https://control.msg91.com/api/v5/otp/verify"


class OtpError(Exception):
    pass


def _mock_active() -> bool:
    return MOCK_EXTERNAL or not MSG91_AUTH_KEY


def generate_and_send(phone: str) -> str:
    """Sends an OTP to `phone`, returns the OTP code ONLY in mock mode
    (in production MSG91 sends it directly to the phone -- the code is
    never returned to the caller)."""
    if _mock_active():
        code = f"{random.randint(0, 9999):04d}"
        print(f"[MOCK OTP] phone={phone} code={code}  (no real SMS sent — set MSG91_AUTH_KEY for production)")
        return code

    try:
        resp = requests.get(
            MSG91_SEND_URL,
            params={"template_id": MSG91_TEMPLATE_ID, "mobile": phone, "authkey": MSG91_AUTH_KEY},
            timeout=5,
        )
        resp.raise_for_status()
        # MSG91 delivers the OTP via SMS; we don't get the code back here.
        return ""
    except requests.RequestException as e:
        raise OtpError(f"Failed to send OTP: {e}") from e


def verify(phone: str, code: str, expected_code: str | None = None) -> bool:
    """In mock mode, checks against the code we generated ourselves.
    In production, delegates to MSG91's verify endpoint."""
    if _mock_active():
        return expected_code is not None and code == expected_code

    try:
        resp = requests.get(
            MSG91_VERIFY_URL,
            params={"mobile": phone, "otp": code, "authkey": MSG91_AUTH_KEY},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("type") == "success"
    except requests.RequestException as e:
        raise OtpError(f"Failed to verify OTP: {e}") from e
