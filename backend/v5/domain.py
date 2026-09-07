import hashlib, json, re, uuid
from datetime import datetime, timezone

FORM_FIELDS = ('full_name age gender city visit_krasnodar phone telegram email preferred_contact public_profile_url occupation life_outside_work interests what_interested event_expectations desired_connections values_in_people barriers_to_meeting social_comfort initiative acquaintance_scenario successful_evening return_reason unacceptable_behavior convenient_days comfortable_price source').split()
class DomainError(Exception):
    def __init__(self, code, status=422): self.code, self.status = code, status
def fingerprint(data):
    safe={k:data.get(k) for k in FORM_FIELDS}
    return hashlib.sha256(json.dumps(safe,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def phone(value):
    digits=re.sub(r'\D','',str(value or ''))
    if len(digits)==11 and digits[0] in '78': digits=digits[1:]
    if len(digits)!=10: raise DomainError('invalid_phone')
    return '+7'+digits
def validate(data):
    if not isinstance(data,dict): raise DomainError('invalid_json',400)
    if data.get('personal_data_consent') is not True: raise DomainError('consent_required')
    if data.get('consent_version')!='CONSENT-PD-2.0' or data.get('policy_version')!='PPD-2.0' or data.get('form_version')!='FORM-2.0': raise DomainError('invalid_legal_version')
    for k in ('full_name','gender','city'):
        if not str(data.get(k,'')).strip(): raise DomainError('missing_'+k)
    try: age=int(data.get('age'))
    except: raise DomainError('invalid_age')
    if not 25<=age<=52: raise DomainError('invalid_age')
    if data['city']!='Краснодар' and not data.get('visit_krasnodar'): raise DomainError('missing_visit_krasnodar')
    email=str(data.get('email',''))
    if email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email): raise DomainError('invalid_email')
    url=str(data.get('public_profile_url',''))
    if url and not re.match(r'^https?://',url,re.I): raise DomainError('invalid_public_profile_url')
    for k in ('desired_connections','convenient_days'):
        if k in data and not isinstance(data[k],list): raise DomainError('invalid_'+k)
    out={k:data.get(k,[] if k in ('desired_connections','convenient_days') else '') for k in FORM_FIELDS};out['age']=age;out['phone']=phone(data.get('phone'));return out
def ids(key):
    h=hashlib.sha256(key.encode()).hexdigest()[:20];return 'APP-'+h,'CONS-'+h
def now(): return datetime.now(timezone.utc).isoformat()
