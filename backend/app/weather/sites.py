"""
VoltAI Site Location Registry

Associates site identifiers with geographic coordinates and timezone information.
Used by weather providers to fetch location-specific weather data.

Design Principles:
  - No coordinates are hard-coded in adapters or business logic.
  - A site location is registered once in SITE_LOCATIONS.
  - Future sites are added here without modifying provider or forecasting code.
  - Coordinates default to a representative Indian renewable-energy region if not set.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class SiteLocation:
    """Geographic location and timezone descriptor for a VoltAI site."""
    site_id: str
    latitude: float
    longitude: float
    timezone: str  # IANA timezone string, e.g. "Asia/Kolkata"
    display_name: str = ""


# ---------------------------------------------------------------------------
# Site Location Registry
# Register all known VoltAI sites here.
# For development/SIH synthetic sites, we use representative Indian locations.
# ---------------------------------------------------------------------------
SITE_LOCATIONS: Dict[str, SiteLocation] = {
    # Synthetic development sites (representative locations in India)
    "site_001": SiteLocation(
        site_id="site_001",
        latitude=23.0225,
        longitude=72.5714,
        timezone="Asia/Kolkata",
        display_name="Ahmedabad Solar Park (Synthetic)",
    ),
    "site_002": SiteLocation(
        site_id="site_002",
        latitude=26.9124,
        longitude=75.7873,
        timezone="Asia/Kolkata",
        display_name="Jaipur Wind Farm (Synthetic)",
    ),
    "site_003": SiteLocation(
        site_id="site_003",
        latitude=13.0827,
        longitude=80.2707,
        timezone="Asia/Kolkata",
        display_name="Chennai Industrial Microgrid (Synthetic)",
    ),
    # Anomaly detection test site
    "site_anom_01": SiteLocation(
        site_id="site_anom_01",
        latitude=28.6139,
        longitude=77.2090,
        timezone="Asia/Kolkata",
        display_name="Delhi Test Site (Anomaly Detection)",
    ),
}

# Default fallback location for unknown sites (Pune, India — centrally located)
DEFAULT_LOCATION = SiteLocation(
    site_id="__default__",
    latitude=18.5204,
    longitude=73.8567,
    timezone="Asia/Kolkata",
    display_name="Default Fallback Location (Pune, India)",
)


def get_site_location(site_id: str) -> SiteLocation:
    """
    Return the registered location for a site, or the default location if unknown.

    Args:
        site_id: VoltAI site identifier.

    Returns:
        SiteLocation with latitude, longitude, and timezone.
    """
    return SITE_LOCATIONS.get(site_id, DEFAULT_LOCATION)


def register_site_location(location: SiteLocation) -> None:
    """
    Dynamically register or update a site location at runtime.
    Useful for tests and future API-driven site management.
    """
    SITE_LOCATIONS[location.site_id] = location
