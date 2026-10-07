"""
shared/geocode.py
------------------
Wraps OpenStreetMap Nominatim for turning a village/town name into lat/lng.

Nominatim usage policy requires a descriptive User-Agent and a max of
1 request/sec — fine for onboarding-time geocoding (rare, not high volume).
Docs: https://nominatim.org/release-docs/latest/api/Overview/

MOCK MODE: if REACH_MOCK_EXTERNAL=1 (or the request fails/times out), returns
a deterministic fallback instead of raising — so local dev and CI don't
depend on outbound network access.
"""

import os
import requests

MOCK_EXTERNAL = os.environ.get("REACH_MOCK_EXTERNAL", "0") == "1"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = f"REACH-waste-platform/0.1 (contact: {os.environ.get('REACH_CONTACT_EMAIL', 'set-REACH_CONTACT_EMAIL-in-.env')})"


class GeocodeError(Exception):
    pass


def geocode_village(name: str, country_hint: str = "India") -> tuple[float, float]:
    """Returns (lat, lng) for a village/town name. Raises GeocodeError if
    it can't be resolved and mock mode is off."""
    if MOCK_EXTERNAL:
        # deterministic fake coordinates so repeated test runs are stable
        fake_lat = 12.0 + (hash(name) % 1000) / 1000.0
        fake_lng = 77.0 + (hash(name) % 1000) / 1000.0
        return (round(fake_lat, 6), round(fake_lng, 6))

    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": f"{name}, {country_hint}", "format": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=5,
        )
        resp.raise_for_status()
        results = resp.json()
        if not results:
            raise GeocodeError(f"No results for '{name}'")
        return (float(results[0]["lat"]), float(results[0]["lon"]))
    except requests.RequestException as e:
        raise GeocodeError(f"Geocoding request failed: {e}") from e
