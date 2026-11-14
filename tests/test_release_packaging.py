"""Unit tests for release zip packaging using small synthetic artifacts."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from pipeline.release.packaging import create_release_zip


def test_create_release_zip_contains_manifest_and_artifact(tmp_path: Path) -> None:
    ephemeris = tmp_path / "ephemeris_v1.json"
    ephemeris.write_text(json.dumps({"schemaVersion": 1, "segments": []}) + "\n")

    output = tmp_path / "dist" / "0.1.0.zip"
    checksums = create_release_zip(
        release_version="0.1.0",
        created_utc="2026-11-14T00:00:00Z",
        pipeline_git_sha="0123456789abcdef0123456789abcdef01234567",
        artifacts=[("ephemeris_v1", ephemeris)],
        output=output,
    )

    assert set(checksums) == {"ephemeris_v1"}
    assert checksums["ephemeris_v1"] == hashlib.sha256(ephemeris.read_bytes()).hexdigest()

    with zipfile.ZipFile(output) as archive:
        assert sorted(archive.namelist()) == [
            "0.1.0/ephemeris_v1.json",
            "0.1.0/manifest.json",
        ]
        manifest = json.loads(archive.read("0.1.0/manifest.json"))
        assert manifest["releaseVersion"] == "0.1.0"
        assert manifest["outputs"][0]["artifact"] == "ephemeris_v1"
        assert manifest["outputs"][0]["sha256"] == checksums["ephemeris_v1"]
