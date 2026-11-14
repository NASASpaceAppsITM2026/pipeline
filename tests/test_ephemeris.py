"""Unit tests for pipeline ephemeris Chebyshev fitting and verification."""

from __future__ import annotations

import numpy as np

from pipeline.ephemeris.fits import (
    eval_chebyshev_scalar,
    eval_chebyshev_vector,
    fit_chebyshev_1d,
    fit_chebyshev_vector,
)
from pipeline.ephemeris.kernels import PINNED_KERNELS


def test_pinned_kernels_metadata() -> None:
    """Verify that all 4 required NAIF SPICE kernels are defined."""
    assert len(PINNED_KERNELS) == 4
    names = {k["name"] for k in PINNED_KERNELS}
    assert "naif0012.tls" in names
    assert "de440.bsp" in names
    assert "moon_pa_de440_200625.bpc" in names
    assert "moon_de440_250416.tf" in names


def test_chebyshev_1d_polynomial_fit() -> None:
    """Verify 1D Chebyshev fit reproduces smooth function to high accuracy."""
    order = 10
    start_t, end_t = 0.0, 10.0
    n = order + 1
    k = np.arange(n)
    x_nodes = np.cos((2 * k + 1) * np.pi / (2 * n))
    t_nodes = 0.5 * (end_t + start_t) + 0.5 * (end_t - start_t) * x_nodes

    # Smooth test function
    func = lambda t: 3.5 * np.sin(0.2 * t) + 1.2 * np.cos(0.5 * t)
    y_nodes = np.array([func(t) for t in t_nodes])

    coeffs = fit_chebyshev_1d(y_nodes, order)
    assert len(coeffs) == n

    for t_test in np.linspace(start_t, end_t, 25):
        approx = eval_chebyshev_scalar(coeffs, t_test, start_t, end_t)
        assert abs(approx - func(t_test)) < 1e-4


def test_chebyshev_vector_polynomial_fit() -> None:
    """Verify 3D Chebyshev fit reproduces 3D trajectory."""
    order = 8
    start_t, end_t = 100.0, 200.0
    n = order + 1
    k = np.arange(n)
    x_nodes = np.cos((2 * k + 1) * np.pi / (2 * n))
    t_nodes = 0.5 * (end_t + start_t) + 0.5 * (end_t - start_t) * x_nodes

    vec_func = lambda t: np.array(
        [
            np.cos(0.01 * t),
            np.sin(0.01 * t),
            0.005 * t,
        ]
    )

    vectors = np.zeros((n, 3))
    for idx, t in enumerate(t_nodes):
        vectors[idx, :] = vec_func(t)

    coeffs = fit_chebyshev_vector(vectors, order)
    assert len(coeffs) == n

    for t_test in np.linspace(start_t, end_t, 20):
        approx = eval_chebyshev_vector(coeffs, t_test, start_t, end_t)
        expected = vec_func(t_test)
        assert np.allclose(approx, expected, atol=1e-5)
