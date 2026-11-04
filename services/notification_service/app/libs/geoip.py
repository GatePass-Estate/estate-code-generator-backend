import logging

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = 3.0  # seconds


async def lookup_ip_location(ip: str) -> str | None:
    """Return a human-readable location string for an IP, e.g. 'Lagos, Nigeria'.

    Returns None if the lookup fails or the IP is private/unknown.
    Uses ipinfo.io free tier (no API key, 50k requests/month).
    """
    if not ip or ip in ("127.0.0.1", "::1", "unknown"):
        return None

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"https://ipinfo.io/{ip}/json")
            if resp.status_code != 200:
                return None
            data = resp.json()

        city = data.get("city")
        country = data.get("country")
        if not city and not country:
            return None
        if city and country:
            return f"{city}, {country}"
        return city or country
    except Exception:
        logger.debug("GeoIP lookup failed for %s", ip, exc_info=True)
        return None
