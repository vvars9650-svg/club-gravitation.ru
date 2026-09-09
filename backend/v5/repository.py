"""In-memory repository used exclusively by V5 unit tests."""

from copy import deepcopy


class RepositoryUnavailable(RuntimeError):
    pass


class FakeRepository:
    """Test double; runtime construction always selects ``YdbRepository``."""

    def __init__(self):
        self.by_key = {}
        self.by_phone = {}
        self.participants = {}
        self.audit = []
        self.blocks = {}

    def get_idempotency(self, key):
        return self.by_key.get(key)

    def resolve_phone(self, phone):
        return self.by_phone.get(phone)

    def save(self, key, record):
        if key in self.by_key:
            return False
        owner = self.by_phone.get(record["form"]["phone"], record["participant_id"])
        if owner in self.blocks:
            raise RepositoryUnavailable("processing_blocked")
        self.by_phone.setdefault(record["form"]["phone"], owner)
        record["participant_id"] = owner
        record["consent"]["participant_id"] = owner
        participant = self.participants.setdefault(owner, {
            "participant_id": owner, "environment": "TEST", "phone": record["form"]["phone"],
            "lifecycle_status": "Новая заявка", "owner": "", "priority": "", "next_action": "",
            "next_contact_at": None, "decision": "", "internal_comment": "",
            "processing_blocked": False, "processing_blocked_at": None,
            "processing_block_reason": "", "processing_block_request_id": "",
        })
        for field in ("full_name", "age", "gender", "city", "visit_krasnodar", "telegram", "email", "preferred_contact", "public_profile_url"):
            participant[field] = record["form"][field]
        self.by_key[key] = deepcopy(record)
        self.audit.append({"request_id": record["request_id"], "application_id": record["application_id"], "participant_id": owner, "operation": "application_created", "status": "ok"})
        return True

    def list_admin_applications(self, filters=None, sort="submitted_at", order="desc"):
        filters = filters or {}
        rows = []
        for record in self.by_key.values():
            if record["environment"] != "TEST":
                continue
            participant, form = self.participants[record["participant_id"]], record["form"]
            row = {"application_id": record["application_id"], "participant_id": record["participant_id"], "submitted_at": record["submitted_at"], "full_name": form["full_name"], "age": form["age"], "city": form["city"], "phone": form["phone"], "telegram": form["telegram"], "preferred_contact": form["preferred_contact"], "environment": "TEST", **{name: participant.get(name) for name in ("lifecycle_status", "owner", "priority", "next_action", "next_contact_at", "decision")}}
            query = str(filters.get("q", "")).strip().lower()
            if query and query not in " ".join(str(row.get(name, "")).lower() for name in ("full_name", "phone", "telegram", "city")):
                continue
            if any(filters.get(name) and row.get(name) != filters[name] for name in ("lifecycle_status", "owner", "priority", "decision")):
                continue
            rows.append(row)
        return sorted(rows, key=lambda row: str(row.get(sort) or ""), reverse=order != "asc")

    def get_admin_participant(self, participant_id):
        participant = self.participants.get(participant_id)
        if not participant or participant.get("environment") != "TEST":
            return None
        applications, consents = [], []
        for record in self.by_key.values():
            if record["participant_id"] != participant_id:
                continue
            applications.append({"application_id": record["application_id"], "submitted_at": record["submitted_at"], "form_version": "FORM-2.0", "request_id": record["request_id"], "form": deepcopy(record["form"])})
            consents.append(deepcopy(record["consent"]))
        return {"environment": "TEST", "participant": deepcopy(participant), "applications": sorted(applications, key=lambda item: item["submitted_at"], reverse=True), "consents": consents}

    def update_admin_participant(self, participant_id, changes, actor, request_id):
        participant = self.participants.get(participant_id)
        if not participant or participant.get("environment") != "TEST":
            return None
        participant.update(changes)
        action = "participant_operational_updated|actor={}|fields={}".format(actor, ",".join(sorted(changes)))
        self.audit.append({"request_id": request_id, "application_id": None, "participant_id": participant_id, "action": action})
        return deepcopy(participant)

    def find_participant(self, participant_id):
        participant = self.participants.get(participant_id)
        return deepcopy(participant) if participant and participant.get("environment") == "TEST" else None

    def find_participant_by_phone(self, phone):
        participant_id = self.by_phone.get(phone)
        return self.find_participant(participant_id) if participant_id else None

    def find_application(self, application_id):
        for record in self.by_key.values():
            if record["application_id"] == application_id and record["environment"] == "TEST":
                return {"application_id": application_id, "participant_id": record["participant_id"], "request_id": record["request_id"]}
        return None

    def block_processing(self, participant_id, request_id="REQ-INTERNAL", reason="internal_lifecycle"):
        participant = self.participants.get(participant_id)
        if not participant or participant.get("environment") != "TEST":
            return False
        if participant_id in self.blocks:
            return False
        self.blocks[participant_id] = {"request_id": request_id, "reason": reason}
        participant.update({"processing_blocked": True, "processing_blocked_at": "TEST-TIMESTAMP", "processing_block_reason": reason, "processing_block_request_id": request_id})
        self.audit.append({"request_id": request_id, "application_id": None, "participant_id": participant_id, "action": "processing_blocked"})
        return True

    def destruction_plan(self, participant_id):
        participant = self.find_participant(participant_id)
        if not participant:
            return None
        records = [record for record in self.by_key.values() if record["participant_id"] == participant_id]
        application_ids = [record["application_id"] for record in records]
        consent_ids = [record["consent"]["consent_id"] for record in records]
        phone_keys = sum(1 for owner in self.by_phone.values() if owner == participant_id)
        audit_count = sum(1 for event in self.audit if event.get("participant_id") == participant_id or event.get("application_id") in application_ids)
        return {"participant_id": participant_id, "dry_run": True, "delete_performed": False, "records": {"participant": {"count": 1, "contains_pii": True, "retention_decision_required": False}, "participant_phone_keys": {"count": phone_keys, "contains_pii": True, "retention_decision_required": False}, "applications": {"count": len(application_ids), "contains_pii": True, "retention_decision_required": False}, "consents": {"count": len(consent_ids), "contains_pii": False, "retention_decision_required": True}, "technical_logs": {"count": len(records), "contains_pii": False, "retention_decision_required": True}, "audit_log": {"count": audit_count, "contains_pii": False, "retention_decision_required": True}}, "application_ids": application_ids, "consent_ids": consent_ids}
