"""Unit tests for terrain horizon mask computation and synthetic geometry."""

from __future__ import annotations

import numpy as np

from pipeline.terrain.masks import (
    MOON_SPHERE_RADIUS_M,
    compute_synthetic_horizon_mask,
    latlon_to_polar_xy,
)


def test_latlon_to_polar_xy_at_pole() -> None:
    """At the exact south pole (-90 deg), polar stereographic X and Y must be 0."""
    x, y = latlon_to_polar_xy(-90.0, 0.0)
    assert abs(x) < 1e-6
    assert abs(y) < 1e-6


def test_latlon_to_polar_xy_offset() -> None:
    """Check distance from south pole for colatitude offset."""
    lat = -89.0
    colat_rad = np.radians(90.0 + lat)  # 1 degree
    expected_dist = 2.0 * MOON_SPHERE_RADIUS_M * np.tan(colat_rad / 2.0)
    x, y = latlon_to_polar_xy(lat, 90.0)
    assert np.isclose(x, expected_dist, atol=1.0)
    assert abs(y) < 1.0


def test_synthetic_flat_terrain_horizon_dip() -> None:
    """Over perfectly flat terrain, horizon angle should equal the curvature dip."""
    obs_h = 2.0  # 2m
    expected_dip = -float(np.degrees(np.sqrt(2.0 * obs_h / MOON_SPHERE_RADIUS_M)))
    # Flat terrain: h(dx, dy) = 0
    flat_func = lambda dx, dy: np.zeros_like(dx)
    mask = compute_synthetic_horizon_mask(
        height_func=flat_func,
        lat_deg=-89.5,
        east_lon_deg=0.0,
        observer_height_m=obs_h,
        max_range_m=5000.0,
    )
    assert len(mask) == 360
    # Over flat sphere, horizon elevation should be within 0.05 deg of geometric dip
    for elev in mask:
        assert abs(elev - expected_dip) < 0.05


def test_synthetic_isolated_peak() -> None:
    """Over flat terrain with an isolated peak due North, horizon should spike at azimuth 0."""
    obs_h = 2.0
    peak_dist = 2000.0  # 2km away
    peak_h = 500.0  # 500m tall

    def terrain_with_peak(dx: np.ndarray, dy: np.ndarray) -> np.ndarray:
        # Peak at dx = 0, dy = peak_dist
        dist_to_peak = np.hypot(dx, dy - peak_dist)
        return peak_h * np.exp(-(dist_to_peak**2) / (2.0 * 200.0**2))

    mask = compute_synthetic_horizon_mask(
        height_func=terrain_with_peak,
        lat_deg=-89.5,
        east_lon_deg=0.0,
        observer_height_m=obs_h,
        max_range_m=5000.0,
    )
    # Peak is at North (azimuth 0)
    north_elev = mask[0]
    expected_peak_angle = np.degrees(np.arctan((peak_h - obs_h) / peak_dist))
    assert abs(north_elev - expected_peak_angle) < 0.5
    # South (azimuth 180) should not see the peak
    assert mask[180] < 0.0
