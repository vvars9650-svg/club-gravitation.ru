import json,re,uuid
from .domain import DomainError
from .service import submit
from .factory import runtime_repository, runtime_photo_upload_service
from .repository import RepositoryConflict, RepositoryUnavailable
from .object_storage import ObjectStorageError
from .admin import admin_handler
from .authorizer import AdminAuthorizationError, authorize_admin
def response(status,body,request_id): return {'statusCode':status,'headers':{'Content-Type':'application/json'},'body':json.dumps({**body,'request_id':request_id},ensure_ascii=False)}

def format_application_number(value):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return str(value).zfill(6)

def is_admin_path(path):
    return bool(re.search(r'(?:^|/)admin(?:/|$)', str(path or '').split('?', 1)[0]))

def handler(event,context=None,repo=None,photo_service=None):
    request_id=getattr(context,'request_id',None) or str(uuid.uuid4())
    # A direct Function call has no Gateway authorizer context and remains
    # closed. Client headers, cookies, body and query parameters are ignored.
    path = event.get('path', '')
    if is_admin_path(path):
        try:
            principal = authorize_admin(event)
        except AdminAuthorizationError as error:
            return response(error.status, {'error': {'code': error.code}}, request_id)
        try:
            admin_repo=repo if repo is not None else runtime_repository()
        except RepositoryUnavailable as e:
            return response(503,{'error':{'code':str(e)}},request_id)
        return admin_handler(event,context,repo=admin_repo,actor_identity=principal.subject)
    if event.get('httpMethod')=='GET' and event.get('path','').endswith('/health'): return response(200,{'status':'synthetic-test-only','environment':'TEST'},request_id)
    if event.get('httpMethod')!='POST': return response(405,{'error':{'code':'method_not_allowed'}},request_id)
    if not str(event.get('headers',{}).get('Content-Type',event.get('headers',{}).get('content-type',''))).startswith('application/json'): return response(415,{'error':{'code':'unsupported_media_type'}},request_id)
    try:
        raw_body=event.get('body','')
        path=event.get('path','')
        if not isinstance(raw_body,str):
            raise DomainError('invalid_json',400)
        if '/photo-uploads/' in path and len(raw_body.encode('utf-8')) > 8192:
            raise DomainError('request_body_too_large',413)
        data=json.loads(raw_body)
        if not isinstance(data,dict):
            raise DomainError('invalid_json',400)
        key=event.get('headers',{}).get('Idempotency-Key') or event.get('headers',{}).get('idempotency-key')
        if path.endswith('/photo-uploads/initiate'):
            if {'photo_data','base64','binary','content'}.intersection(data):
                raise DomainError('photo_binary_not_allowed',400)
            repo=repo or runtime_repository()
            service=photo_service or runtime_photo_upload_service(context,repo)
            return response(201,service.initiate(key),request_id)
        if path.endswith('/photo-uploads/complete'):
            repo=repo or runtime_repository()
            service=photo_service or runtime_photo_upload_service(context,repo)
            return response(200,service.complete(data.get('photo_object_id'),key),request_id)
        repo=repo or runtime_repository()
        record,replay=submit(data,key,repo,request_id)
        application_number = format_application_number(record.get('application_number'))
        if application_number is None:
            return response(503, {'error': {'code': 'application_number_unavailable'}}, request_id)
        return response(200 if replay else 201,{'application_id':record['application_id'],'application_number':application_number,'participant_id':record['participant_id'],'idempotent_replay':replay,'environment':'TEST'},request_id)
    except RepositoryConflict as e:
        return response(409, {'error': {'code': str(e)}}, request_id)
    except RepositoryUnavailable as e:
        code = str(e)
        return response(409 if code == 'processing_blocked' else 503, {'error': {'code': code}}, request_id)
    except ObjectStorageError as e:
        return response(503, {'error': {'code': str(e)}}, request_id)
    except (ValueError,DomainError) as e:
        code=e.code if isinstance(e,DomainError) else 'invalid_json';status=e.status if isinstance(e,DomainError) else 400;return response(status,{'error':{'code':code}},request_id)
