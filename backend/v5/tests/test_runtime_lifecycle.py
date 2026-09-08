import concurrent.futures
import threading
import unittest
from unittest import mock

from backend.v5 import factory
from backend.v5.handler import handler
from backend.v5.repository import FakeRepository, RepositoryUnavailable
from backend.v5.tests.test_v5 import e


class RuntimeRepositoryLifecycleTests(unittest.TestCase):
    def setUp(self):
        factory._runtime_repository_instance = None

    def tearDown(self):
        factory._runtime_repository_instance = None

    def test_two_posts_reuse_one_runtime_repository(self):
        repository = FakeRepository()

        with mock.patch.object(
            factory,
            "_create_runtime_repository",
            return_value=repository,
        ) as create:
            first = handler(e(k="runtime-one"))
            second = handler(e(k="runtime-two"))

        self.assertEqual(first["statusCode"], 201)
        self.assertEqual(second["statusCode"], 201)
        create.assert_called_once_with()

    def test_health_does_not_create_repository(self):
        with mock.patch.object(
            factory,
            "_create_runtime_repository",
        ) as create:
            result = handler(
                {"httpMethod": "GET", "path": "/health"}
            )

        self.assertEqual(result["statusCode"], 200)
        create.assert_not_called()
        self.assertIsNone(factory._runtime_repository_instance)

    def test_failed_initialization_is_not_cached(self):
        repository = FakeRepository()

        with mock.patch.object(
            factory,
            "_create_runtime_repository",
            side_effect=[
                RepositoryUnavailable("bad_configuration"),
                repository,
            ],
        ) as create:
            failed = handler(e(k="runtime-failed"))
            recovered = handler(e(k="runtime-recovered"))

        self.assertEqual(failed["statusCode"], 503)
        self.assertEqual(recovered["statusCode"], 201)
        self.assertEqual(create.call_count, 2)
        self.assertIs(factory._runtime_repository_instance, repository)

    def test_concurrent_initialization_creates_one_repository(self):
        repository = FakeRepository()
        entered = threading.Event()
        release = threading.Event()

        def create_repository():
            entered.set()
            release.wait(timeout=5)
            return repository

        with mock.patch.object(
            factory,
            "_create_runtime_repository",
            side_effect=create_repository,
        ) as create:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=2
            ) as executor:
                first = executor.submit(factory.runtime_repository)
                self.assertTrue(entered.wait(timeout=5))
                second = executor.submit(factory.runtime_repository)
                release.set()
                instances = [first.result(), second.result()]

        self.assertEqual(instances, [repository, repository])
        create.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
