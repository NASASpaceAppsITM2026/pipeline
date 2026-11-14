"""Unit tests for the release manifest writer and validator (synthetic examples)."""

from __future__ import annotations

import pytest

from pipeline.release import ManifestError, validate_manifest, write_manifest

VALID_SYNTHETIC_MANIFEST: dict = {
    "releaseVersion": "0.1.0",
    "createdUtc": "2026-11-14T00:00:00Z",
    "pipelineGitSha": "0123456789abcdef0123456789abcdef01234567",
    "inputs": [],
    "outputs": [
        {
            "artifact": "ephemeris_v1",
            "fileName": "ephemeris_v1.json",
            "sha256": "0" * 64,
            "bytes": 512,
        },
    ],
}


def test_validate_accepts_valid_synthetic_manifest() -> None:
    assert validate_manifest(VALID_SYNTHETIC_MANIFEST) == []


def test_write_manifest_returns_documented_fields() -> None:
    manifest = write_manifest(
        release_version="0.1.0",
        created_utc="2026-11-14T00:00:00Z",
        pipeline_git_sha="0123456789abcdef0123456789abcdef01234567",
        inputs=[],
        outputs=[
            {
                "artifact": "ephemeris_v1",
                "fileName": "ephemeris_v1.json",
                "sha256": "0" * 64,
                "bytes": 512,
            },
        ],
    )
    assert manifest["releaseVersion"] == "0.1.0"
    assert manifest["createdUtc"] == "2026-11-14T00:00:00Z"
    assert manifest["pipelineGitSha"] == "0123456789abcdef0123456789abcdef01234567"
    assert manifest["inputs"] == []
    assert manifest["outputs"][0]["artifact"] == "ephemeris_v1"


def test_write_manifest_rejects_invalid_document() -> None:
    with pytest.raises(ManifestError):
        write_manifest(
            release_version="not-a-semver",
            created_utc="2026-11-14T00:00:00Z",
            pipeline_git_sha="too-short",
            inputs=[],
            outputs=[],
        )


def test_validate_rejects_missing_release_version() -> None:
    manifest = dict(VALID_SYNTHETIC_MANIFEST)
    del manifest["releaseVersion"]
    errors = validate_manifest(manifest)
    assert any("releaseVersion" in error for error in errors)


def test_validate_rejects_bad_checksum() -> None:
    manifest = {
        "releaseVersion": "0.1.0",
        "createdUtc": "2026-11-14T00:00:00Z",
        "pipelineGitSha": "0123456789abcdef0123456789abcdef01234567",
        "inputs": [],
        "outputs": [
            {
                "artifact": "ephemeris_v1",
                "fileName": "ephemeris_v1.json",
                "sha256": "not-a-checksum",
                "bytes": 512,
            },
        ],
    }
    errors = validate_manifest(manifest)
    assert any("sha256" in error for error in errors)


def test_validate_rejects_bad_pipeline_git_sha() -> None:
    manifest = dict(VALID_SYNTHETIC_MANIFEST)
    manifest["pipelineGitSha"] = "deadbeef"
    errors = validate_manifest(manifest)
    assert any("pipelineGitSha" in error for error in errors)
