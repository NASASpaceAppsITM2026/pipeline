"""Release manifest writer and validator aligned with ``docs/data-contracts.md``."""

from __future__ import annotations

import re
from typing import Any

SCHEMA_VERSION = 1
CHECKSUM_LENGTH = 64
GIT_SHA_LENGTH = 40
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
GIT_SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")

INPUT_KIND_SPICE_KERNEL = "spice_kernel"
INPUT_KIND_DEM = "dem"


class ManifestError(ValueError):
    """Raised when a release manifest violates the data contract."""


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and SHA256_PATTERN.fullmatch(value) is not None


def _is_git_sha(value: object) -> bool:
    return isinstance(value, str) and GIT_SHA_PATTERN.fullmatch(value) is not None


def _is_positive_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _validate_input(index: int, entry: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(entry, dict):
        return [f"'inputs[{index}]' must be an object"]

    kind = entry.get("type")
    if kind == INPUT_KIND_SPICE_KERNEL:
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"'inputs[{index}]' with type 'spice_kernel' requires a non-empty 'name'")
        if not _is_sha256(entry.get("sha256")):
            errors.append(
                f"'inputs[{index}]' with type 'spice_kernel' requires a 64-character hex 'sha256'"
            )
    elif kind == INPUT_KIND_DEM:
        product_name = entry.get("productName")
        if not isinstance(product_name, str) or not product_name.strip():
            errors.append(f"'inputs[{index}]' with type 'dem' requires a non-empty 'productName'")
        version = entry.get("version")
        if not isinstance(version, str) or not version.strip():
            errors.append(f"'inputs[{index}]' with type 'dem' requires a non-empty 'version'")
        if not _is_sha256(entry.get("sha256")):
            errors.append(f"'inputs[{index}]' with type 'dem' requires a 64-character hex 'sha256'")
        if not _is_positive_number(entry.get("resolutionM")):
            errors.append(
                f"'inputs[{index}]' with type 'dem' requires a positive numeric 'resolutionM'"
            )
    else:
        errors.append(f"'inputs[{index}]' has unsupported type {kind!r}")

    return errors


def _validate_output(index: int, entry: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(entry, dict):
        return [f"'outputs[{index}]' must be an object"]

    artifact = entry.get("artifact")
    if not isinstance(artifact, str) or not artifact.strip():
        errors.append(f"'outputs[{index}]' requires a non-empty 'artifact'")

    file_name = entry.get("fileName")
    if not isinstance(file_name, str) or not file_name.strip():
        errors.append(f"'outputs[{index}]' requires a non-empty 'fileName'")

    if not _is_sha256(entry.get("sha256")):
        errors.append(f"'outputs[{index}]' requires a 64-character hex 'sha256'")

    byte_count = entry.get("bytes")
    if not isinstance(byte_count, int) or isinstance(byte_count, bool) or byte_count < 0:
        errors.append(f"'outputs[{index}]' requires a non-negative integer 'bytes'")

    return errors


def write_manifest(
    *,
    release_version: str,
    created_utc: str,
    pipeline_git_sha: str,
    inputs: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a release manifest document and validate it before returning it."""
    manifest: dict[str, Any] = {
        "releaseVersion": release_version,
        "createdUtc": created_utc,
        "pipelineGitSha": pipeline_git_sha,
        "inputs": inputs,
        "outputs": outputs,
    }
    errors = validate_manifest(manifest)
    if errors:
        raise ManifestError("invalid release manifest: " + "; ".join(errors))
    return manifest


def validate_manifest(manifest: object) -> list[str]:
    """Validate a release manifest against the data contract.

    Returns a list of human-readable error strings; an empty list means the
    manifest is valid.
    """
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["release manifest must be a JSON object"]

    release_version = manifest.get("releaseVersion")
    if not isinstance(release_version, str) or not SEMVER_PATTERN.fullmatch(release_version):
        errors.append("'releaseVersion' must be a semantic version string such as '1.0.0'")

    created_utc = manifest.get("createdUtc")
    if not isinstance(created_utc, str) or not created_utc.endswith("Z"):
        errors.append("'createdUtc' must be an ISO-8601 UTC string ending in 'Z'")

    pipeline_git_sha = manifest.get("pipelineGitSha")
    if not isinstance(pipeline_git_sha, str) or not GIT_SHA_PATTERN.fullmatch(pipeline_git_sha):
        errors.append("'pipelineGitSha' must be a full 40-character commit SHA")

    inputs = manifest.get("inputs")
    if not isinstance(inputs, list):
        errors.append("'inputs' must be an array")
    else:
        for index, entry in enumerate(inputs):
            errors.extend(_validate_input(index, entry))

    outputs = manifest.get("outputs")
    if not isinstance(outputs, list):
        errors.append("'outputs' must be an array")
    else:
        for index, entry in enumerate(outputs):
            errors.extend(_validate_output(index, entry))

    return errors
