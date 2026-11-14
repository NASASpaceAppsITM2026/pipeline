"""NAIF SPICE kernel management and loading for ephemeris generation.

Checksums and versions are pinned per docs/DATA.md and docs/data-contracts.md.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path

import spiceypy as spice

PINNED_KERNELS = (
    {
        "name": "naif0012.tls",
        "sha256": "678E32BDB5A744117A467CD9601CD6B373F0E9BC9BBDE1371D5EEE39600A039B",
        "url": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/lsk/naif0012.tls",
    },
    {
        "name": "de440.bsp",
        "sha256": "A4CE9BF9B3282BECC9F4B2AC3CEBE03A2AE7599981AABD7265FD8482FFF7C4B5",
        "url": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440.bsp",
    },
    {
        "name": "moon_pa_de440_200625.bpc",
        "sha256": "60CD55AA401EA2EA97360636F567554BFE4E37BB829F901B4460A455DFAF783F",
        "url": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/moon_pa_de440_200625.bpc",
    },
    {
        "name": "moon_de440_250416.tf",
        "sha256": "A47C71E9C9F33796BDAFB2C9D69A7EE447B6016ECAD80F71CD6F3E479F9CF768",
        "url": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/satellites/moon_de440_250416.tf",
    },
)


def compute_sha256(path: Path) -> str:
    """Compute uppercase SHA-256 hex digest of a file."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest().upper()


def verify_kernel(kernel_path: Path, expected_sha256: str) -> None:
    """Verify that a kernel file exists and matches its expected SHA-256 checksum."""
    if not kernel_path.is_file():
        raise FileNotFoundError(f"Missing required SPICE kernel: {kernel_path}")
    actual_sha256 = compute_sha256(kernel_path)
    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"Checksum mismatch for {kernel_path.name}: "
            f"expected {expected_sha256}, got {actual_sha256}"
        )


def find_kernel_path(kernel_name: str, search_dirs: Sequence[Path]) -> Path:
    """Find a kernel file across candidate directories."""
    for d in search_dirs:
        candidate = d / kernel_name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"SPICE kernel {kernel_name} not found in search paths: {search_dirs}")


def furnish_kernels(search_dirs: Sequence[Path]) -> list[Path]:
    """Verify and load pinned NAIF SPICE kernels into SPICE via spiceypy.furnsh."""
    loaded_paths: list[Path] = []
    for entry in PINNED_KERNELS:
        kernel_path = find_kernel_path(entry["name"], search_dirs)
        verify_kernel(kernel_path, entry["sha256"])
        spice.furnsh(str(kernel_path))
        loaded_paths.append(kernel_path)
    return loaded_paths


def unload_kernels() -> None:
    """Clear all loaded SPICE kernels from memory."""
    spice.kclear()


def download_kernels() -> None:
    """Download pinned NAIF SPICE kernels into data/raw/."""
    # Offline-first rule (AGENTS.md): No network in automated builds.
    # When kernels are absent, this explains where to place them.
    raise NotImplementedError(
        "Automated download is disabled in offline mode. "
        "Place pinned SPICE kernels in RawData/ or data/raw/ per docs/DATA.md."
    )
