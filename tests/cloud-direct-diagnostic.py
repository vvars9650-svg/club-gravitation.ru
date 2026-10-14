"""Replay only the saved synthetic E2E request through the real TEST repository."""
import os
import json
import ydb
from backend.v5.ydb_repository import YdbRepository
from backend.v5.handler import handler

event=json.load(open('test-results/cloud-failed-request.json',encoding='utf-8'))
payload=json.loads(event['body'])
assert payload['email'].endswith('@example.test') and payload['full_name']=='Synthetic Release Test'
with ydb.Driver(endpoint=os.environ['YDB_ENDPOINT'],database=os.environ['YDB_DATABASE'],credentials=ydb.AccessTokenCredentials(os.environ['YC_TOKEN'])) as driver:
    driver.wait(timeout=15,fail_fast=True)
    repo=YdbRepository(driver=driver)
    try:
        result=handler(event,repo=repo)
        print(json.dumps(result))
    finally:
        repo.pool.stop()
