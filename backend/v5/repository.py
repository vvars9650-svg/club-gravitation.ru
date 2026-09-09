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
        self.blocks = set()

    def get_idempotency(self, key):
        return self.by_key.get(key)

    def resolve_phone(self, phone):
        return self.by_phone.get(phone)

    def save(self, key, record):
        if key in self.by_key:
            return False
        owner = self.by_phone.setdefault(record["form"]["phone"], record["participant_id"])
        record["participant_id"] = owner
        record["consent"]["participant_id"] = owner
        if owner in self.blocks:
            raise RepositoryUnavailable("processing_blocked")
        participant = self.participants.setdefault(owner, {
            "participant_id": owner, "environment": "TEST", "phone": record["form"]["phone"],
            "lifecycle_status": "Новая заявка", "owner": "", "priority": "", "next_action": "",
            "next_contact_at": None, "decision": "", "internal_comment": "",
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

    def block_processing(self, participant_id):
        self.blocks.add(participant_id)

    def destruction_plan(self, participant_id):
        return {"participant_id": participant_id, "applications": "separate command required", "consent_evidence": "retention policy required"}
