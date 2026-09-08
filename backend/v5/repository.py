class RepositoryUnavailable(RuntimeError): pass
class FakeRepository:
    def __init__(self): self.by_key={};self.by_phone={};self.participants={};self.audit=[];self.blocks=set()
    def get_idempotency(self,key): return self.by_key.get(key)
    def resolve_phone(self,phone): return self.by_phone.get(phone)
    def save(self,key,record):
        if key in self.by_key: return False
        owner=self.by_phone.setdefault(record['form']['phone'],record['participant_id']);record['participant_id']=owner
        if owner in self.blocks: raise RepositoryUnavailable('processing_blocked')
        self.by_key[key]=record;self.participants.setdefault(owner,{'phone':record['form']['phone'],'lifecycle_status':'new'});self.audit.append({'request_id':record['request_id'],'application_id':record['application_id'],'operation':'application_created','status':'ok'});return True
    def block_processing(self,participant_id): self.blocks.add(participant_id)
    def destruction_plan(self,participant_id): return {'participant_id':participant_id,'applications':'separate command required','consent_evidence':'retention policy required'}
