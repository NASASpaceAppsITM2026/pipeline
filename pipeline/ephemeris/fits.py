"""Build Chebyshev ephemeris fits for Moon->Sun and Moon->Earth apparent directions.

Produces ephemeris_v1 artifacts matching docs/data-contracts.md §4.
All calculations use MOON_ME frame, TDB time scale, and apparent (LT+S) aberration correction.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import spiceypy as spice

from pipeline.ephemeris.kernels import PINNED_KERNELS, furnish_kernels, unload_kernels


def fit_chebyshev_1d(values_at_nodes: np.ndarray, order: int) -> list[float]:
    """Compute Chebyshev polynomial coefficients from function values at Chebyshev Gauss nodes."""
    n = order + 1
    k = np.arange(n)
    coeffs: list[float] = []
    for i in range(n):
        factor = 1.0 / n if i == 0 else 2.0 / n
        basis = np.cos(i * (2 * k + 1) * np.pi / (2 * n))
        c_i = factor * float(np.sum(values_at_nodes * basis))
        coeffs.append(c_i)
    return coeffs


def fit_chebyshev_vector(vectors_at_nodes: np.ndarray, order: int) -> list[list[float]]:
    """Compute Chebyshev polynomial coefficients for a 3D vector series."""
    # vectors_at_nodes has shape (N, 3)
    n = order + 1
    direction_coeffs: list[list[float]] = []
    for comp in range(3):
        comp_coeffs = fit_chebyshev_1d(vectors_at_nodes[:, comp], order)
        if comp == 0:
            direction_coeffs = [[c] for c in comp_coeffs]
        else:
            for i, c in enumerate(comp_coeffs):
                direction_coeffs[i].append(c)
    assert len(direction_coeffs) == n
    return direction_coeffs


def eval_chebyshev_vector(
    coeffs: Sequence[Sequence[float]], t: float, start_t: float, end_t: float
) -> np.ndarray:
    """Evaluate 3D Chebyshev series at time t."""
    span = end_t - start_t
    x = np.clip((2.0 * (t - start_t)) / span - 1.0, -1.0, 1.0)
    order = len(coeffs) - 1
    vec = np.zeros(3)
    for i in range(order + 1):
        t_i = np.cos(i * np.arccos(x))
        vec += np.array(coeffs[i]) * t_i
    return vec


def eval_chebyshev_scalar(coeffs: Sequence[float], t: float, start_t: float, end_t: float) -> float:
    """Evaluate 1D Chebyshev series at time t."""
    span = end_t - start_t
    x = np.clip((2.0 * (t - start_t)) / span - 1.0, -1.0, 1.0)
    order = len(coeffs) - 1
    val = 0.0
    for i in range(order + 1):
        t_i = np.cos(i * np.arccos(x))
        val += coeffs[i] * t_i
    return float(val)


def query_body_spice(target_id: str, et: float) -> tuple[np.ndarray, float]:
    """Query SPICE for Moon->target apparent position in MOON_ME frame.

    Returns unit direction vector and distance in km.
    """
    state, _lt = spice.spkezr(target_id, et, "MOON_ME", "LT+S", "301")
    pos = np.array(state[:3], dtype=np.float64)
    dist = float(np.linalg.norm(pos))
    if dist <= 0:
        raise ValueError(f"SPICE returned zero distance for target {target_id} at ET {et}")
    unit_dir = pos / dist
    return unit_dir, dist


def fit_segment(
    target_id: str,
    start_et: float,
    end_et: float,
    order: int,
) -> dict[str, Any]:
    """Fit a single segment for a body pair using Chebyshev polynomials."""
    n = order + 1
    k = np.arange(n)
    # Chebyshev Gauss nodes in [-1, 1]
    x_nodes = np.cos((2 * k + 1) * np.pi / (2 * n))
    # Map to [start_et, end_et]
    et_nodes = 0.5 * (end_et + start_et) + 0.5 * (end_et - start_et) * x_nodes

    directions = np.zeros((n, 3), dtype=np.float64)
    distances = np.zeros(n, dtype=np.float64)

    for idx, et in enumerate(et_nodes):
        u_dir, dist = query_body_spice(target_id, et)
        directions[idx, :] = u_dir
        distances[idx] = dist

    dir_coeffs = fit_chebyshev_vector(directions, order)
    dist_coeffs = fit_chebyshev_1d(distances, order)

    return {
        "order": order,
        "direction": dir_coeffs,
        "distanceKm": dist_coeffs,
    }


def measure_fit_error_deg(
    target_id: str,
    segment: dict[str, Any],
    start_et: float,
    end_et: float,
    num_check_points: int = 50,
) -> float:
    """Measure maximum direction error in degrees between Chebyshev fit and SPICE."""
    check_times = np.linspace(start_et, end_et, num_check_points)
    max_err_deg = 0.0
    dir_coeffs = segment["direction"]

    for et in check_times:
        true_u, _ = query_body_spice(target_id, et)
        fitted_vec = eval_chebyshev_vector(dir_coeffs, et, start_et, end_et)
        norm = np.linalg.norm(fitted_vec)
        if norm > 0:
            fitted_u = fitted_vec / norm
            dot = np.clip(np.dot(true_u, fitted_u), -1.0, 1.0)
            err_deg = float(np.degrees(np.arccos(dot)))
            max_err_deg = max(max_err_deg, err_deg)

    return max_err_deg


def build_ephemeris_fits(
    kernels_dirs: Sequence[Path] | None = None,
    output_path: Path | None = None,
    start_utc: str = "2026-01-01T00:00:00Z",
    end_utc: str = "2027-01-01T00:00:00Z",
    segment_duration_hours: float = 48.0,
    chebyshev_order: int = 10,
) -> dict[str, Any]:
    """Generate ephemeris_v1 artifact over the specified window and write to output_path."""
    if kernels_dirs is None:
        search_paths = [
            Path("/home/kevin/Kevin/NASA2026/RawData"),
            Path("/home/kevin/Kevin/NASA2026/data/raw"),
            Path("data/raw"),
        ]
    else:
        search_paths = list(kernels_dirs)

    furnish_kernels(search_paths)
    try:
        start_et = float(spice.str2et(start_utc))
        end_et = float(spice.str2et(end_utc))
        segment_duration_sec = segment_duration_hours * 3600.0

        num_segments = int(np.ceil((end_et - start_et) / segment_duration_sec))
        overall_max_err_deg = 0.0

        segments: list[dict[str, Any]] = []

        targets = [
            ("MOON_TO_SUN", "10"),
            ("MOON_TO_EARTH", "399"),
        ]

        for body_pair, target_id in targets:
            for s_idx in range(num_segments):
                seg_start = start_et + s_idx * segment_duration_sec
                seg_end = min(end_et, seg_start + segment_duration_sec)
                if seg_end <= seg_start:
                    continue

                cheb_fit = fit_segment(target_id, seg_start, seg_end, chebyshev_order)
                err_deg = measure_fit_error_deg(target_id, cheb_fit, seg_start, seg_end)
                overall_max_err_deg = max(overall_max_err_deg, err_deg)

                segments.append(
                    {
                        "bodyPair": body_pair,
                        "startEpochTdbSec": seg_start,
                        "endEpochTdbSec": seg_end,
                        "chebyshev": cheb_fit,
                    }
                )

        kernel_entries = [{"name": k["name"], "sha256": k["sha256"]} for k in PINNED_KERNELS]

        artifact: dict[str, Any] = {
            "schemaVersion": 1,
            "header": {
                "schemaVersion": 1,
                "kernels": kernel_entries,
                "frame": "MOON_ME",
                "aberrationCorrection": "apparent",
                "timeScale": "TDB",
                "units": {
                    "time": "TDB seconds",
                    "direction": "degrees",
                    "distance": "kilometers",
                },
                "supportedStartEpochTdbSec": start_et,
                "supportedEndEpochTdbSec": end_et,
                "fitErrorDirectionDeg": 0.001,
                "fitErrorMeasuredDirectionDeg": overall_max_err_deg,
            },
            "segments": segments,
        }

        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w", encoding="utf-8") as f:
                json.dump(artifact, f, indent=2)

        return artifact
    finally:
        unload_kernels()
