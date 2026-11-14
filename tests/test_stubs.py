"""Unit tests for remaining stub entry points."""

from __future__ import annotations

import pytest

from pipeline.ephemeris.fits import build_ephemeris_fits
from pipeline.ephemeris.kernels import download_kernels


@pytest.mark.parametrize(
    "stub",
    [download_kernels, build_ephemeris_fits],
    ids=["download_kernels", "build_ephemeris_fits"],
)
def test_stub_entry_points_raise_not_implemented(stub: object) -> None:
    with pytest.raises(NotImplementedError):
        stub()  # type: ignore[operator]
