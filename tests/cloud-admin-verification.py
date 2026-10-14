"""Synthetic-only TEST repository/Admin contract verification; not OIDC UI acceptance."""
import os, json, urllib.request
from types import SimpleNamespace
from io import BytesIO
from PIL import Image
import ydb
from backend.v5.ydb_repository import YdbRepository
from backend.v5.admin import admin_handler
from backend.v5.factory import runtime_photo_reader

proof=json.load(open('test-results/cloud-e2e.json',encoding='utf-8'))
assert proof['environment']=='TEST'
with ydb.Driver(endpoint=os.environ['YDB_ENDPOINT'],database=os.environ['YDB_DATABASE'],credentials=ydb.AccessTokenCredentials(os.environ['YC_TOKEN'])) as driver:
    driver.wait(timeout=15,fail_fast=True)
    repo=YdbRepository(driver=driver)
    try:
        card=repo.get_admin_application(proof['application_id'])
        app=card['application']
        assert app['form']['email'].endswith('@example.test') and app['form']['full_name']=='Synthetic Release Test'
        assert card['consents'][0]['form_version']=='FORM-2.3'
        assert card['consents'][0]['consent_text_hash'].startswith('TEST-')
        assert app['duplicate_attempt_count']>=1
        reader=runtime_photo_reader(SimpleNamespace(token=os.environ['YC_TOKEN']),repo)
        photo=reader(app)
        assert photo and photo['expires_in']==180
        with urllib.request.urlopen(photo['url']) as response:
            image=response.read(100000)
            assert response.status==200
            decoded=Image.open(BytesIO(image))
            decoded.verify()
        patch=admin_handler({'httpMethod':'PATCH','path':'/admin/applications/'+proof['application_id'],'headers':{'Content-Type':'application/json'},'body':json.dumps({'owner':'Влад','internal_comment':'Synthetic release verification'})},repo=repo,actor_identity='synthetic-release-verification')
        assert patch['statusCode']==200, patch['body']
        unauthorized=urllib.request.Request('https://d5ds805l71s68liu6ge4.fovt0b64.apigw.yandexcloud.net/admin/participants/'+proof['application_id']+'?include_photo=true')
        try:
            urllib.request.urlopen(unauthorized)
            raise AssertionError('unauthenticated admin accepted')
        except urllib.error.HTTPError as error:
            assert error.code in (401,403)
        result={'environment':'TEST','application_id':proof['application_id'],'evidence':'PASS','private_photo_get':'PASS','photo_ttl':180,'admin_repository_patch':'PASS','unauthenticated_gateway':'PASS','operator_oidc_ui':'NOT_VERIFIED'}
        print(json.dumps(result))
        open('test-results/cloud-admin.json','w',encoding='utf-8').write(json.dumps(result,indent=2))
    finally:
        repo.pool.stop()
