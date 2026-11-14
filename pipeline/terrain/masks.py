"""LOLA-based horizon mask computation for lunar landing sites.

Produces horizon_masks_v1 artifacts matching docs/data-contracts.md §5.
Computes horizon elevation angles over 360 azimuths with lunar sphere curvature
and observer height included.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

MOON_SPHERE_RADIUS_M = 1737400.0
MOON_SPHERE_RADIUS_KM = 1737.4
DEM_RESOLUTION_M = 20.0
DEM_LINES = 30400
DEM_SAMPLES = 30400
LINE_OFFSET = 15199.5
SAMPLE_OFFSET = 15199.5
SCALING_FACTOR = 0.5
KNOWN_DEM_SHA256 = "DB44C3B2444ACFF1AF528301C8A6988934B490249ACEFF0AC55668BDF3EAB365"

DEFAULT_CANDIDATE_SITES: tuple[dict[str, Any], ...] = (
    {
        "id": "apollo11",
        "name": "Apollo 11",
        "latDeg": 0.674,
        "eastLonDeg": 23.45,
    },
    {
        "id": "south_pole_895",
        "name": "South Pole 89.5S",
        "latDeg": -89.5,
        "eastLonDeg": 0.0,
    },
    {
        "id": "south_pole_summer",
        "name": "South Pole 89.5S 180E",
        "latDeg": -89.5,
        "eastLonDeg": 180.0,
    },
    {
        "id": "shackleton_connecting_ridge",
        "name": "Shackleton Connecting Ridge",
        "latDeg": -89.9,
        "eastLonDeg": 120.0,
    },
    {
        "id": "de_gerlache_rim",
        "name": "de Gerlache Rim",
        "latDeg": -88.5,
        "eastLonDeg": -88.0,
    },
    {
        "id": "malapert_mountain",
        "name": "Malapert Mountain",
        "latDeg": -86.0,
        "eastLonDeg": 2.7,
    },
    {
        "id": "haworth_crater_rim",
        "name": "Haworth Rim",
        "latDeg": -87.4,
        "eastLonDeg": -5.0,
    },
)


def latlon_to_polar_xy(lat_deg: float, east_lon_deg: float) -> tuple[float, float]:
    """Convert south-polar planetocentric lat/lon to Polar Stereographic X/Y in meters."""
    # Polar stereographic true at south pole (lat = -90 deg)
    colat_rad = np.radians(90.0 + lat_deg)
    r = 2.0 * MOON_SPHERE_RADIUS_M * np.tan(colat_rad / 2.0)
    lon_rad = np.radians(east_lon_deg)
    x = r * np.sin(lon_rad)
    y = -r * np.cos(lon_rad)
    return float(x), float(y)


def compute_site_horizon_mask(
    dem_memmap: np.ndarray,
    lat_deg: float,
    east_lon_deg: float,
    observer_height_m: float = 2.0,
    max_range_km: float = 50.0,
    azimuth_step_deg: float = 1.0,
) -> tuple[list[float], str]:
    """Ray-march terrain horizon mask for a site across azimuths.

    Returns list of horizon elevations in degrees and status ('ok' or 'missing_coverage').
    """
    # LDEM_80S covers latitudes from -80 to -90 deg
    if lat_deg > -80.0:
        # Outside DEM coverage: return flat spherical horizon with dip
        # Dip angle = -sqrt(2 * h / R) in radians
        dip_deg = -float(np.degrees(np.sqrt(2.0 * observer_height_m / MOON_SPHERE_RADIUS_M)))
        num_az = round(360.0 / azimuth_step_deg)
        return [round(dip_deg, 4)] * num_az, "missing_coverage"

    x0, y0 = latlon_to_polar_xy(lat_deg, east_lon_deg)

    # Elevation at site
    s0 = int(np.clip(SAMPLE_OFFSET + x0 / DEM_RESOLUTION_M, 0, DEM_SAMPLES - 1))
    l0 = int(np.clip(LINE_OFFSET - y0 / DEM_RESOLUTION_M, 0, DEM_LINES - 1))
    h0 = float(dem_memmap[l0, s0]) * SCALING_FACTOR
    z_obs = h0 + observer_height_m

    azimuths = np.arange(0.0, 360.0, azimuth_step_deg)
    # Range steps: 100m to max_range_km in 200m increments
    ranges = np.arange(100.0, max_range_km * 1000.0, 200.0)
    az_rad = np.radians(azimuths)

    # Local frame orientation in projected (X, Y)
    norm0 = np.hypot(x0, y0)
    if norm0 > 0:
        north_u = np.array([-x0 / norm0, -y0 / norm0])
    else:
        north_u = np.array([0.0, 1.0])
    # East is 90 deg clockwise from North in right-handed ENU
    east_u = np.array([north_u[1], -north_u[0]])

    az_grid, r_grid = np.meshgrid(az_rad, ranges, indexing="ij")
    dx = r_grid * np.sin(az_grid)
    dy = r_grid * np.cos(az_grid)

    px = x0 + dx * east_u[0] + dy * north_u[0]
    py = y0 + dx * east_u[1] + dy * north_u[1]

    s_grid = np.clip(SAMPLE_OFFSET + px / DEM_RESOLUTION_M, 0, DEM_SAMPLES - 1).astype(int)
    l_grid = np.clip(LINE_OFFSET - py / DEM_RESOLUTION_M, 0, DEM_LINES - 1).astype(int)

    h_terrain = dem_memmap[l_grid, s_grid].astype(np.float32) * SCALING_FACTOR
    curv_drop = (r_grid**2) / (2.0 * MOON_SPHERE_RADIUS_M)

    angles_rad = np.arctan((h_terrain - z_obs - curv_drop) / r_grid)
    mask_deg = np.degrees(np.max(angles_rad, axis=1))

    # Curvature horizon lower bound (dip)
    dip_deg = -float(np.degrees(np.sqrt(2.0 * observer_height_m / MOON_SPHERE_RADIUS_M)))
    clamped_mask = [float(round(max(elev, dip_deg), 4)) for elev in mask_deg]

    return clamped_mask, "ok"


def compute_synthetic_horizon_mask(
    height_func: Any,
    lat_deg: float,
    east_lon_deg: float,
    observer_height_m: float = 2.0,
    max_range_m: float = 10000.0,
    azimuth_step_deg: float = 1.0,
) -> list[float]:
    """Compute horizon mask over a synthetic continuous terrain height function."""
    h0 = float(height_func(0.0, 0.0))
    z_obs = h0 + observer_height_m

    azimuths = np.arange(0.0, 360.0, azimuth_step_deg)
    ranges = np.arange(50.0, max_range_m, 50.0)
    az_rad = np.radians(azimuths)

    az_grid, r_grid = np.meshgrid(az_rad, ranges, indexing="ij")
    dx = r_grid * np.sin(az_grid)
    dy = r_grid * np.cos(az_grid)

    h_terrain = height_func(dx, dy)
    curv_drop = (r_grid**2) / (2.0 * MOON_SPHERE_RADIUS_M)
    angles_rad = np.arctan((h_terrain - z_obs - curv_drop) / r_grid)
    mask_deg = np.degrees(np.max(angles_rad, axis=1))
    return [float(round(val, 4)) for val in mask_deg]


def build_horizon_masks(
    dem_path: Path | None = None,
    output_path: Path | None = None,
    sites: Sequence[dict[str, Any]] | None = None,
    observer_height_m: float = 2.0,
    max_range_km: float = 50.0,
    azimuth_step_deg: float = 1.0,
) -> dict[str, Any]:
    """Build horizon_masks_v1 artifact for candidate landing sites."""
    candidate_sites = list(sites if sites is not None else DEFAULT_CANDIDATE_SITES)

    if dem_path is None:
        dem_path = Path("/home/kevin/Kevin/NASA2026/RawData/ldem_80s_20m.img")

    if not dem_path.is_file():
        raise FileNotFoundError(f"LOLA DEM file not found at {dem_path}")

    dem_memmap = np.memmap(dem_path, dtype="<i2", mode="r", shape=(DEM_LINES, DEM_SAMPLES))

    site_records: list[dict[str, Any]] = []
    for site in candidate_sites:
        elevations, status = compute_site_horizon_mask(
            dem_memmap=dem_memmap,
            lat_deg=site["latDeg"],
            east_lon_deg=site["eastLonDeg"],
            observer_height_m=observer_height_m,
            max_range_km=max_range_km,
            azimuth_step_deg=azimuth_step_deg,
        )
        site_records.append(
            {
                "id": site["id"],
                "eastLonDeg": site["eastLonDeg"],
                "latDeg": site["latDeg"],
                "elevationDeg": elevations,
                "status": status,
            }
        )

    artifact: dict[str, Any] = {
        "schemaVersion": 1,
        "header": {
            "schemaVersion": 1,
            "demProductName": "LDEM_80S_20M",
            "demVersion": "1.0",
            "demSha256": KNOWN_DEM_SHA256,
            "resolutionM": int(DEM_RESOLUTION_M),
            "sphereRadiusKm": MOON_SPHERE_RADIUS_KM,
            "observerHeightKm": observer_height_m / 1000.0,
            "azimuthStepDeg": azimuth_step_deg,
            "maxRayRangeKm": max_range_km,
            "status": "ok",
        },
        "sites": site_records,
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(artifact, f, indent=2)

    return artifact
