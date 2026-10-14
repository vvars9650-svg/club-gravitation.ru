import os
from .domain import validate,fingerprint,ids,now,DomainError,FORM_VERSION,CONSENT_VERSION,POLICY_VERSION,SHORT_FORM_VERSION,legal_versions
from .legal_text import consent_hash_for_version
def submit(data,key,repo,request_id,consent_hash=None,max_attempts=3):
    if not key: raise DomainError('idempotency_key_required',400)
    form=validate(data);fp=fingerprint(form, data["consent_version"] if data["form_version"] == SHORT_FORM_VERSION else None);old=repo.get_idempotency(key)
    if old:
        if old['payload_fingerprint']!=fp: raise DomainError('idempotency_conflict',409)
        return old,True
    # Preserve old records/replays, but stale 2.2 browser tabs must not create
    # evidence for 2.2 after the public legal routes have switched to 2.3.
    if getattr(repo, 'environment', 'TEST') == 'PROD' and data['form_version'] == FORM_VERSION and os.getenv('V5_ALLOW_LEGACY_INTAKE') != 'true':
        raise DomainError('legacy_form_retired_reload_required',409)
    consent_version,policy_version=legal_versions(data["form_version"])
    consent_hash=consent_hash_for_version(consent_version, getattr(repo,"environment","TEST"))
    application_id,consent_id=ids(key);participant_id='PT-'+application_id[4:]
    record={'environment':'TEST','application_id':application_id,'participant_id':participant_id,'consent_id':consent_id,'photo_object_id':form['photo_object_id'],'form':form,'payload_fingerprint':fp,'submitted_at':now(),'request_id':request_id,'consent':{'participant_id':participant_id,'application_id':application_id,'consent_id':consent_id,'consent_type':'personal_data_application','consent_version':consent_version,'policy_version':policy_version,'form_version':data['form_version'],'consent_text_hash':consent_hash,'granted':True,'granted_at':now(),'source':'website','request_id':request_id}}
    record['form_version'] = data['form_version']
    record['environment'] = getattr(repo, 'environment', 'TEST')
    for _ in range(max_attempts):
        if repo.save(key,record):
            return record,False
        old=repo.get_idempotency(key)
        if old:
            if old['payload_fingerprint']!=fp: raise DomainError('idempotency_conflict',409)
            return old,True
    raise DomainError('concurrency_retry_exhausted',503)
    return record,False

