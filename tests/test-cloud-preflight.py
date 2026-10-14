"""Read only TEST schema metadata. Credentials arrive through environment."""
import os
import json
import ydb

with ydb.Driver(endpoint=os.environ['YDB_ENDPOINT'], database=os.environ['YDB_DATABASE'], credentials=ydb.AccessTokenCredentials(os.environ['YC_TOKEN'])) as driver:
    driver.wait(timeout=15, fail_fast=True)
    with ydb.QuerySessionPool(driver) as pool:
        def query(session):
            with session.transaction().execute('SELECT migration_id FROM schema_migrations WHERE environment="TEST";', commit_tx=True) as reader:
                return sorted(row['migration_id'] for result in reader for row in result.rows)
        print(json.dumps({'test_migrations':pool.retry_operation_sync(query)}))
