"""Package a lunar navigation data release into a release zip and print checksums."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from pipeline.release.packaging import create_release_zip


def _default_created_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Package lunar navigation data release artifacts plus manifest.json into a release zip.",
    )
    parser.add_argument(
        "--release-version", required=True, help="Release version in semver format, e.g. 1.0.0"
    )
    parser.add_argument(
        "--pipeline-git-sha", required=True, help="Full commit SHA of the pipeline repository"
    )
    parser.add_argument(
        "--created-utc", default=None, help="ISO-8601 UTC timestamp, e.g. 2026-11-14T00:00:00Z"
    )
    parser.add_argument(
        "--output", type=Path, default=None, help="Release zip path, e.g. dist/1.0.0.zip"
    )
    parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="Artifact to include, repeatable, e.g. ephemeris_v1=/abs/path/to/ephemeris_v1.json",
    )
    args = parser.parse_args(argv)

    if not args.artifact:
        parser.error("--artifact is required (format: NAME=PATH)")

    artifacts: list[tuple[str, Path]] = []
    for spec in args.artifact:
        name, separator, raw_path = spec.partition("=")
        if not separator or not name.strip() or not raw_path.strip():
            parser.error(f"--artifact must be in NAME=PATH format, got {spec!r}")
        artifacts.append((name.strip(), Path(raw_path.strip())))

    output = args.output if args.output is not None else Path(f"dist/{args.release_version}.zip")
    checksums = create_release_zip(
        release_version=args.release_version,
        created_utc=args.created_utc or _default_created_utc(),
        pipeline_git_sha=args.pipeline_git_sha,
        artifacts=artifacts,
        output=output,
    )
    for artifact in sorted(checksums):
        print(f"{artifact} {checksums[artifact]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
