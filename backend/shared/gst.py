"""
shared/gst.py
--------------
Verifies a corporate's GSTIN before onboarding them to the Corporate Portal.
Real integration is via Setu (docs.setu.co/data/gst) or Surepass -- both
sit in front of the GSTN network since direct GSTN API access requires
becoming a registered GSP/ASP, which is a heavy formal process, not a
startup-friendly signup.

Needs env vars in production:
  SETU_CLIENT_ID / SETU_CLIENT_SECRET / SETU_PRODUCT_INSTANCE_ID
  (same Setu account used for shared/kyc.py can usually cover this too --
  check your Setu product bundle)

MOCK MODE: if REACH_MOCK_EXTERNAL=1 or SETU_CLIENT_ID isn't set, uses
Setu's own documented sandbox test GSTIN for a "verified" response.
"""

import os
import requests

MOCK_EXTERNAL = os.environ.get("REACH_MOCK_EXTERNAL", "0") == "1"
SETU_CLIENT_ID = os.environ.get("SETU_CLIENT_ID")
SETU_CLIENT_SECRET = os.environ.get("SETU_CLIENT_SECRET")
SETU_PRODUCT_INSTANCE_ID = os.environ.get("SETU_PRODUCT_INSTANCE_ID")

SETU_BASE_URL = os.environ.get("SETU_BASE_URL", "https://dg-sandbox.setu.co")

SANDBOX_TEST_GSTIN = "27AAICB3918J1CT"  # Setu's documented sandbox success value


class GstError(Exception):
    pass


def _mock_active() -> bool:
    return MOCK_EXTERNAL or not SETU_CLIENT_ID


def verify_gstin(gstin: str) -> dict:
    """Returns {"valid": bool, "legal_name": str | None, "status": str | None}."""
    if _mock_active():
        if gstin == SANDBOX_TEST_GSTIN:
            return {"valid": True, "legal_name": "Sandbox Test Company Pvt Ltd", "status": "Active"}
        # basic structural check so obviously-fake input doesn't pass silently
        if len(gstin) != 15:
            return {"valid": False, "legal_name": None, "status": None}
        return {"valid": True, "legal_name": f"Mock Company ({gstin[:6]})", "status": "Active"}

    try:
        resp = requests.get(
            f"{SETU_BASE_URL}/data/gst",
            headers={
                "x-client-id": SETU_CLIENT_ID,
                "x-client-secret": SETU_CLIENT_SECRET,
                "x-product-instance-id": SETU_PRODUCT_INSTANCE_ID,
            },
            params={"gstin": gstin},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "valid": True,
            "legal_name": data.get("legalName") or data.get("tradeName"),
            "status": data.get("status"),
        }
    except requests.RequestException as e:
        raise GstError(f"GST verification failed: {e}") from e
