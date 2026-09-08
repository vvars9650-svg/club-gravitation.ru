import os
import threading

from .repository import RepositoryUnavailable


_runtime_repository_instance = None
_runtime_repository_lock = threading.Lock()


def runtime_repository():
    global _runtime_repository_instance

    if os.getenv("V5_REPOSITORY") == "fake":
        raise RepositoryUnavailable("fake_repository_for_tests_only")

    if _runtime_repository_instance is not None:
        return _runtime_repository_instance

    with _runtime_repository_lock:
        if _runtime_repository_instance is not None:
            return _runtime_repository_instance

        # Assign only after successful construction. Configuration or
        # connection failures must remain retryable on a later invocation.
        repository = _create_runtime_repository()
        _runtime_repository_instance = repository
        return repository


def _create_runtime_repository():
    from .ydb_repository import YdbRepository

    return YdbRepository()
