import json,uuid
from .domain import DomainError
from .service import submit
from .repository import FakeRepository
_repo=FakeRepository()
def response(status,body,request_id): return {'statusCode':status,'headers':{'Content-Type':'application/json'},'body':json.dumps({**body,'request_id':request_id},ensure_ascii=False)}
def handler(event,context=None,repo=None):
    request_id=getattr(context,'request_id',None) or str(uuid.uuid4());repo=repo or _repo
    if event.get('httpMethod')=='GET' and event.get('path','').endswith('/health'): return response(200,{'status':'synthetic-test-only','environment':'TEST'},request_id)
    if event.get('httpMethod')!='POST': return response(405,{'error':{'code':'method_not_allowed'}},request_id)
    if not str(event.get('headers',{}).get('Content-Type',event.get('headers',{}).get('content-type',''))).startswith('application/json'): return response(415,{'error':{'code':'unsupported_media_type'}},request_id)
    try:
        data=json.loads(event.get('body','')); key=event.get('headers',{}).get('Idempotency-Key') or event.get('headers',{}).get('idempotency-key');record,replay=submit(data,key,repo,request_id)
        return response(200 if replay else 201,{'application_id':record['application_id'],'participant_id':record['participant_id'],'idempotent_replay':replay,'environment':'TEST'},request_id)
    except (ValueError,DomainError) as e:
        code=e.code if isinstance(e,DomainError) else 'invalid_json';status=e.status if isinstance(e,DomainError) else 400;return response(status,{'error':{'code':code}},request_id)
