import os
from .repository import RepositoryUnavailable
def runtime_repository():
    if os.getenv('V5_REPOSITORY')=='fake': raise RepositoryUnavailable('fake_repository_for_tests_only')
    from .ydb_repository import YdbRepository
    return YdbRepository()
