import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from backend.v5.build_deployment import build_deployment_zip


EXPECTED_DEPLOYMENT_FILES = {
    "index.py",
    "requirements.txt",
    "v5/__init__.py",
    "v5/domain.py",
    "v5/service.py",
    "v5/repository.py",
    "v5/ydb_repository.py",
    "v5/factory.py",
    "v5/admin.py",
    "v5/handler.py",
}


class DeploymentPackageTests(unittest.TestCase):
    def test_zip_layout_import_and_health_without_ydb_configuration(self):
        with tempfile.TemporaryDirectory(
            prefix="gravitation-v5-smoke-"
        ) as tmp:
            temp_dir = Path(tmp)
            archive_path = build_deployment_zip(
                temp_dir / "v5-deployment.zip"
            )

            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(
                    set(archive.namelist()),
                    EXPECTED_DEPLOYMENT_FILES,
                )
                extracted = temp_dir / "extracted"
                archive.extractall(extracted)

            environment = os.environ.copy()
            environment.pop("YDB_ENDPOINT", None)
            environment.pop("YDB_DATABASE", None)
            environment.pop("V5_TEST_CONSENT_TEXT_HASH", None)
            environment.pop("PYTHONPATH", None)

            smoke_code = """
import json
from pathlib import Path
import index

assert Path(index.__file__).resolve().parent == Path.cwd().resolve()
assert callable(index.handler)
response = index.handler({"httpMethod": "GET", "path": "/health"})
assert response["statusCode"] == 200
body = json.loads(response["body"])
assert body["status"] == "synthetic-test-only"
assert body["environment"] == "TEST"
"""

            result = subprocess.run(
                [sys.executable, "-c", smoke_code],
                cwd=extracted,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                ),
            )


if __name__ == "__main__":
    unittest.main()
