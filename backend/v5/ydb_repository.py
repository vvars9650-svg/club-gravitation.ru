"""YDB-only repository. Imported lazily so unit tests need no SDK or cloud."""
import json, os
from .repository import RepositoryUnavailable
class YdbRepository:
    def __init__(self, endpoint=None, database=None, consent_hash=None, driver=None):
        self.endpoint=endpoint or os.getenv('YDB_ENDPOINT');self.database=database or os.getenv('YDB_DATABASE');self.consent_hash=consent_hash or os.getenv('V5_TEST_CONSENT_TEXT_HASH')
        if not self.endpoint or not self.database or not self.consent_hash: raise RepositoryUnavailable('missing_ydb_test_configuration')
        if not self.consent_hash.startswith('TEST-'): raise RepositoryUnavailable('consent_hash_must_be_test_marked')
        if driver is None:
            import ydb
            driver=ydb.Driver(endpoint=self.endpoint,database=self.database);driver.wait(fail_fast=True,timeout=10)
        self.driver=driver
    def get_idempotency(self,key): return None # reads occur inside save transaction for cross-instance correctness
    def resolve_phone(self,phone): return None
    def save(self,key,record):
        """One serializable transaction must read idempotency+phone key then write all six tables.
        Adapter integration is intentionally fail-closed until deploy review supplies the SDK transaction binding."""
        raise RepositoryUnavailable('ydb_transaction_binding_required')
    def find_participant(self, participant_id): raise RepositoryUnavailable('ydb_transaction_binding_required')
    def block_processing(self, participant_id): raise RepositoryUnavailable('ydb_transaction_binding_required')
    def destruction_plan(self, participant_id): return {'participant_id':participant_id,'applications':'separate command required','consents':'retention policy required','audit_log':'retention policy required'}
