"""Unit tests for the bootstrap stub entry points (no science implemented yet)."""

from __future__ import annotations

import pytest

from pipeline.ephemeris.fits import build_ephemeris_fits
from pipeline.ephemeris.kernels import download_kernels
from pipeline.terrain.masks import build_horizon_masks


@pytest.mark.parametrize(
    "stub",
    [download_kernels, build_ephemeris_fits, build_horizon_masks],
    ids=["download_kernels", "build_ephemeris_fits", "build_horizon_masks"],
)
def test_stub_entry_points_raise_not_implemented(stub: object) -> None:
    with pytest.raises(NotImplementedError):
        stub()  # type: ignore[operator]
