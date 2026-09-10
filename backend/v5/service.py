from .domain import validate,fingerprint,ids,now,DomainError,FORM_VERSION,CONSENT_VERSION,POLICY_VERSION
def submit(data,key,repo,request_id,consent_hash='TEST-CONFIGURED-NONCANONICAL',max_attempts=3):
    if not key: raise DomainError('idempotency_key_required',400)
    form=validate(data);fp=fingerprint(form);old=repo.get_idempotency(key)
    if old:
        if old['payload_fingerprint']!=fp: raise DomainError('idempotency_conflict',409)
        return old,True
    application_id,consent_id=ids(key);participant_id=repo.resolve_phone(form['phone']) or 'PT-'+application_id[4:]
    record={'environment':'TEST','application_id':application_id,'participant_id':participant_id,'consent_id':consent_id,'form':form,'payload_fingerprint':fp,'submitted_at':now(),'request_id':request_id,'consent':{'participant_id':participant_id,'application_id':application_id,'consent_id':consent_id,'consent_type':'personal_data_application','consent_version':CONSENT_VERSION,'policy_version':POLICY_VERSION,'form_version':FORM_VERSION,'consent_text_hash':consent_hash,'granted':True,'granted_at':now(),'source':'website','request_id':request_id}}
    for _ in range(max_attempts):
        if repo.save(key,record): return record,False
        old=repo.get_idempotency(key)
        if old:
            if old['payload_fingerprint']!=fp: raise DomainError('idempotency_conflict',409)
            return old,True
    raise DomainError('concurrency_retry_exhausted',503)
    return record,False

