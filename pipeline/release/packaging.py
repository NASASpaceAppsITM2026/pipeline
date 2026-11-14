"""Release packaging: artifacts plus a release manifest into a release zip."""

from __future__ import annotations

import hashlib
import json
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pipeline.release.manifest import write_manifest


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_release_zip(
    *,
    release_version: str,
    created_utc: str,
    pipeline_git_sha: str,
    artifacts: Sequence[tuple[str, Path]],
    output: Path,
) -> dict[str, str]:
    """Write ``manifest.json`` plus the given artifacts into a release zip.

    ``artifacts`` is a sequence of ``(artifact_identifier, source_path)`` pairs.

    Returns a mapping of artifact identifier to SHA-256 hex digest of the artifact file.
    """
    outputs: list[dict[str, Any]] = []
    checksums: dict[str, str] = {}
    for artifact, path in artifacts:
        digest = _sha256_of(path)
        checksums[artifact] = digest
        outputs.append(
            {
                "artifact": artifact,
                "fileName": path.name,
                "sha256": digest,
                "bytes": path.stat().st_size,
            }
        )

    manifest = write_manifest(
        release_version=release_version,
        created_utc=created_utc,
        pipeline_git_sha=pipeline_git_sha,
        inputs=[],
        outputs=outputs,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{release_version}/manifest.json", json.dumps(manifest, indent=2) + "\n")
        for _artifact, path in artifacts:
            archive.write(path, arcname=f"{release_version}/{path.name}")

    return checksums
