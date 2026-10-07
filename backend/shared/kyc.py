"""
shared/kyc.py
--------------
Wraps Setu's Offline Aadhaar eKYC (OKYC) API for collector identity
verification -- this is the real KYC step (separate from phone OTP).
Docs: https://docs.setu.co/data/okyc/api-integration

Real Setu OKYC flow has more steps than this module exposes (create request,
initiate with captcha, verify with OTP) -- this wraps it down to two calls
that match our own OTP pattern:
  1. initiate_ekyc(aadhaar_number)  -> reference_id  (sends OTP to Aadhaar-linked mobile)
  2. verify_ekyc(reference_id, otp) -> {verified, name, dob, gender}

Needs env vars in production:
  SETU_CLIENT_ID
  SETU_CLIENT_SECRET
  SETU_PRODUCT_INSTANCE_ID

MOCK MODE: if REACH_MOCK_EXTERNAL=1 or SETU_CLIENT_ID isn't set, no real
UIDAI call is made -- a fake but structurally correct response is returned,
using Setu's own documented sandbox test Aadhaar number (999999990019) as
the trigger for a "successful" mock verification.
"""

import os
import uuid
import requests

MOCK_EXTERNAL = os.environ.get("REACH_MOCK_EXTERNAL", "0") == "1"
SETU_CLIENT_ID = os.environ.get("SETU_CLIENT_ID")
SETU_CLIENT_SECRET = os.environ.get("SETU_CLIENT_SECRET")
SETU_PRODUCT_INSTANCE_ID = os.environ.get("SETU_PRODUCT_INSTANCE_ID")

SETU_BASE_URL = os.environ.get("SETU_BASE_URL", "https://dg-sandbox.setu.co")

SANDBOX_TEST_AADHAAR = "999999990019"  # Setu's documented sandbox success value


class KycError(Exception):
    pass


def _mock_active() -> bool:
    return MOCK_EXTERNAL or not SETU_CLIENT_ID


def _headers():
    return {
        "x-client-id": SETU_CLIENT_ID,
        "x-client-secret": SETU_CLIENT_SECRET,
        "x-product-instance-id": SETU_PRODUCT_INSTANCE_ID,
        "Content-Type": "application/json",
    }


def initiate_ekyc(aadhaar_number: str) -> str:
    """Starts Aadhaar eKYC -- sends an OTP to the Aadhaar-linked mobile
    number. Returns a reference_id to pass to verify_ekyc."""
    if _mock_active():
        return f"mock-okyc-{uuid.uuid4()}"

    try:
        resp = requests.post(
            f"{SETU_BASE_URL}/okyc/request",
            headers=_headers(),
            json={"aadhaarNumber": aadhaar_number},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["id"]
    except requests.RequestException as e:
        raise KycError(f"Failed to initiate eKYC: {e}") from e


def verify_ekyc(reference_id: str, aadhaar_number: str, otp: str) -> dict:
    """Verifies the OTP and returns the Aadhaar-derived identity data on
    success: {verified, name, dob, gender}."""
    if _mock_active():
        if aadhaar_number == SANDBOX_TEST_AADHAAR:
            return {
                "verified": True,
                "name": "Test Collector (mock eKYC)",
                "dob": "1990-01-01",
                "gender": "M",
            }
        return {"verified": False, "name": None, "dob": None, "gender": None}

    try:
        resp = requests.post(
            f"{SETU_BASE_URL}/okyc/{reference_id}/verify",
            headers=_headers(),
            json={"aadhaarNumber": aadhaar_number, "otp": otp},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "verified": True,
            "name": data.get("name"),
            "dob": data.get("dob"),
            "gender": data.get("gender"),
        }
    except requests.RequestException as e:
        raise KycError(f"Failed to verify eKYC: {e}") from e
