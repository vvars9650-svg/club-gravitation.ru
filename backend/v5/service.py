from .domain import validate,fingerprint,ids,now,DomainError
def submit(data,key,repo,request_id,consent_hash='TEST-CONFIGURED-NONCANONICAL'):
    if not key: raise DomainError('idempotency_key_required',400)
    form=validate(data);fp=fingerprint(form);old=repo.get_idempotency(key)
    if old:
        if old['payload_fingerprint']!=fp: raise DomainError('idempotency_conflict',409)
        return old,True
    application_id,consent_id=ids(key);participant_id=repo.resolve_phone(form['phone']) or 'PT-'+application_id[4:]
    record={'environment':'TEST','application_id':application_id,'participant_id':participant_id,'consent_id':consent_id,'form':form,'payload_fingerprint':fp,'submitted_at':now(),'request_id':request_id,'consent':{'participant_id':participant_id,'application_id':application_id,'consent_id':consent_id,'consent_type':'personal_data_application','consent_version':'CONSENT-PD-2.0','policy_version':'PPD-2.0','form_version':'FORM-2.0','consent_text_hash':consent_hash,'granted':True,'granted_at':now(),'source':'website','request_id':request_id}}
    if not repo.save(key,record): return submit(data,key,repo,request_id,consent_hash)
    return record,False
