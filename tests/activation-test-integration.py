"""Explicit synthetic-only TEST data-plane check; no function deployment."""
import base64, json, os, uuid, urllib.request
from pathlib import Path
import ydb
from backend.v5.ydb_repository import YdbRepository
from backend.v5.handler import handler
from backend.v5.legal_text import CURRENT_CONSENT_TEXT_SHA256

TEST_API='https://d5ds805l71s68liu6ge4.fovt0b64.apigw.yandexcloud.net'
key='legal-activation-'+str(uuid.uuid4())

def post(path, payload):
    req=urllib.request.Request(TEST_API+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Idempotency-Key':key},method='POST')
    with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)

assert os.environ['V5_TEST_PHOTO_BUCKET']=='gravitation-v5-test-photos-b1g4bdjb'
assert os.environ.get('V5_ENVIRONMENT','TEST')=='TEST'
with ydb.Driver(endpoint=os.environ['YDB_ENDPOINT'],database=os.environ['YDB_DATABASE'],credentials=ydb.AccessTokenCredentials(os.environ['YC_TOKEN'])) as driver:
    driver.wait(timeout=15,fail_fast=True)
    repo=YdbRepository(driver=driver,environment='TEST')
    try:
        old=repo.get_admin_application('APP-4e006298e63d34b163d6')['consents']
        initiated=post('/photo-uploads/initiate',{})
        assert initiated['upload_url'].startswith('https://storage.yandexcloud.net/gravitation-v5-test-photos-b1g4bdjb/')
        png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
        with urllib.request.urlopen(urllib.request.Request(initiated['upload_url'],data=png,headers={'Content-Type':'image/png'},method='PUT'),timeout=30) as response:assert response.status==200
        photo=post('/photo-uploads/complete',{'photo_object_id':initiated['photo_object_id']})
        payload={'full_name':'Synthetic Legal Activation 2.3','age':30,'gender':'Мужчина','city':'Краснодар','visit_krasnodar':'','phone':'+79990002323','email':'legal-activation@example.test','profile_or_messenger_url':'@synthetic_legal_activation','photo_object_id':photo['photo_object_id'],'policy_acknowledged':True,'personal_data_consent':True,'form_version':'FORM-2.3','consent_version':'CONSENT-PD-2.3','policy_version':'PPD-2.3'}
        event={'httpMethod':'POST','path':'/applications','headers':{'Content-Type':'application/json','Idempotency-Key':key},'body':json.dumps(payload)}
        response=handler(event,repo=repo)
        assert response['statusCode'] in (200,201),json.loads(response['body']).get('error')
        result=json.loads(response['body'])
        card=repo.get_admin_application(result['application_id'])
        consent=card['consents'][0]
        assert (consent['form_version'],consent['consent_version'],consent['policy_version'])==('FORM-2.3','CONSENT-PD-2.3','PPD-2.3')
        assert consent['consent_text_hash']=='TEST-'+CURRENT_CONSENT_TEXT_SHA256
        assert repo.get_admin_application('APP-4e006298e63d34b163d6')['consents']==old
        assert json.loads(handler(event,repo=repo)['body'])['application_number']==result['application_number']
        proof={'environment':'TEST','path':'existing TEST private photo API + local activation handler + real TEST YDB','application_id':result['application_id'],'application_number':result['application_number'],'legal_versions':['FORM-2.3','CONSENT-PD-2.3','PPD-2.3'],'consent_hash':consent['consent_text_hash'],'legacy_000018_evidence_unchanged':True,'replay':'PASS','cloud_deployment':False}
        Path('test-results').mkdir(exist_ok=True)
        Path('test-results/activation-2.3-integration.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
        print(json.dumps(proof))
    finally:repo.pool.stop()
