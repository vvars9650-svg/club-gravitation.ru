"""Build the GRAVITATION V5 Yandex Cloud Function deployment ZIP."""

import argparse
import shutil
import tempfile
import zipfile
from pathlib import Path


SOURCE_DIR = Path(__file__).resolve().parent
PACKAGE_FILES = (
    "__init__.py",
    "domain.py",
    "service.py",
    "repository.py",
    "ydb_repository.py",
    "factory.py",
    "handler.py",
)
EXPECTED_FILES = (
    "index.py",
    "requirements.txt",
    *(f"v5/{name}" for name in PACKAGE_FILES),
)


def build_deployment_zip(output_path):
    """Create a deployment ZIP using an explicit safe file allowlist."""
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="gravitation-v5-build-") as tmp:
        staging = Path(tmp)
        package_dir = staging / "v5"
        package_dir.mkdir()

        shutil.copy2(SOURCE_DIR / "deployment" / "index.py", staging)
        shutil.copy2(SOURCE_DIR / "requirements.txt", staging)

        for name in PACKAGE_FILES:
            shutil.copy2(SOURCE_DIR / name, package_dir / name)

        with zipfile.ZipFile(
            output_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            for relative_name in EXPECTED_FILES:
                archive.write(
                    staging / Path(relative_name),
                    arcname=relative_name,
                )

    return output_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=SOURCE_DIR / "dist" / "v5-deployment.zip",
    )
    args = parser.parse_args()
    print(build_deployment_zip(args.output))


if __name__ == "__main__":
    main()
