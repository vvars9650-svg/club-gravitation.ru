"""In-memory repository used exclusively by V5 unit tests."""

import hashlib
from copy import deepcopy
from threading import RLock

from .domain import phone as normalize_phone
from .participant_model import INITIAL_APPLICATION_STATUS, INITIAL_PARTICIPANT_STATUS
from .photo_contract import ALLOWED_IMAGE_FORMATS, validate_photo_object_id


class RepositoryUnavailable(RuntimeError):
    pass


class RepositoryConflict(RuntimeError):
    pass


DESTRUCTION_CLASSIFICATION = {
    "participant": {"contains_personal_data": True, "contains_direct_contact_data": True, "contains_linkable_identifiers": True, "retention_decision_required": False},
    "participant_phone_keys": {"contains_personal_data": True, "contains_direct_contact_data": True, "contains_linkable_identifiers": True, "retention_decision_required": False},
    "applications": {"contains_personal_data": True, "contains_direct_contact_data": True, "contains_linkable_identifiers": True, "retention_decision_required": False},
    "consents": {"contains_personal_data": True, "contains_direct_contact_data": False, "contains_linkable_identifiers": True, "retention_decision_required": True},
    "technical_logs": {"contains_personal_data": True, "contains_direct_contact_data": False, "contains_linkable_identifiers": True, "retention_decision_required": True},
    "audit_log": {"contains_personal_data": True, "contains_direct_contact_data": False, "contains_linkable_identifiers": True, "retention_decision_required": True},
}
PHOTO_DESTRUCTION_CLASSIFICATION = {"contains_personal_data": True, "contains_direct_contact_data": False, "contains_linkable_identifiers": True, "retention_decision_required": False}


class FakeRepository:
    """Test double; runtime construction always selects ``YdbRepository``."""

    def __init__(self):
        self.by_key = {}
        self.by_phone = {}
        self.participants = {}
        self.audit = []
        self.blocks = {}
        self.migrations = set()
        self.photo_objects = {}
        self._lock = RLock()

    @staticmethod
    def _context_hash(upload_context):
        return hashlib.sha256(str(upload_context).encode("utf-8")).hexdigest()

    def register_photo_upload(
        self,
        photo_object_id,
        upload_context,
        detected_format="jpeg",
        byte_size=1024,
    ):
        """Register metadata for a locally normalized synthetic TEST photo."""
        photo_object_id = validate_photo_object_id(photo_object_id)
        if detected_format not in ALLOWED_IMAGE_FORMATS or not 0 < byte_size <= 10 * 1024 * 1024:
            raise ValueError("invalid_normalized_photo_metadata")
        with self._lock:
            if photo_object_id in self.photo_objects:
                raise RepositoryConflict("photo_object_id_conflict")
            self.photo_objects[photo_object_id] = {
                "photo_object_id": photo_object_id,
                "storage_key": "test-protected/" + photo_object_id,
                "lifecycle_state": "READY",
                "owner_context_hash": self._context_hash(upload_context),
                "application_id": None,
                "participant_id": None,
                "detected_format": detected_format,
                "mime_type": ALLOWED_IMAGE_FORMATS[detected_format],
                "byte_size": byte_size,
                "metadata_stripped": True,
                "created_at": "TEST-TIMESTAMP",
                "deleted_at": None,
            }
        return photo_object_id

    def create_photo_upload(self, photo_object_id, storage_key, owner_context_hash):
        """Persist only opaque identifiers and the already-hashed owner context."""
        photo_object_id = validate_photo_object_id(photo_object_id)
        with self._lock:
            if photo_object_id in self.photo_objects:
                raise RepositoryConflict("photo_object_id_conflict")
            self.photo_objects[photo_object_id] = {
                "environment": "TEST",
                "photo_object_id": photo_object_id,
                "storage_key": storage_key,
                "lifecycle_state": "PENDING_UPLOAD",
                "owner_context_hash": owner_context_hash,
                "application_id": None,
                "participant_id": None,
                "detected_format": "",
                "mime_type": "",
                "byte_size": 0,
                "metadata_stripped": False,
                "created_at": "TEST-TIMESTAMP",
                "deleted_at": None,
            }
        return photo_object_id

    def get_photo_upload(self, photo_object_id):
        with self._lock:
            photo = self.photo_objects.get(photo_object_id)
            return deepcopy(photo) if photo else None

    def mark_photo_ready(self, photo_object_id, owner_context_hash, metadata):
        with self._lock:
            photo = self.photo_objects.get(photo_object_id)
            if not photo or photo["owner_context_hash"] != owner_context_hash:
                raise RepositoryConflict("photo_reference_not_owned")
            if photo["lifecycle_state"] == "READY":
                return deepcopy(photo)
            if photo["lifecycle_state"] != "PENDING_UPLOAD":
                raise RepositoryConflict("photo_reference_not_available")
            photo.update({
                "lifecycle_state": "READY",
                "detected_format": metadata["detected_format"],
                "mime_type": metadata["mime_type"],
                "byte_size": metadata["byte_size"],
                "metadata_stripped": True,
            })
            return deepcopy(photo)

    def reject_photo_upload(self, photo_object_id, lifecycle_state):
        with self._lock:
            photo = self.photo_objects.get(photo_object_id)
            if photo and photo["lifecycle_state"] != "READY":
                photo["lifecycle_state"] = lifecycle_state
            return bool(photo)

    def reserve_photo_for_submission(self, photo_object_id, upload_context, application_id):
        with self._lock:
            photo = self.photo_objects.get(photo_object_id)
            if not photo:
                raise RepositoryConflict("photo_reference_not_found")
            if photo["owner_context_hash"] != self._context_hash(upload_context):
                raise RepositoryConflict("photo_reference_not_owned")
            if photo["lifecycle_state"] == "RESERVED" and photo["application_id"] == application_id:
                return True
            if photo["lifecycle_state"] != "READY" or photo["application_id"] is not None:
                raise RepositoryConflict("photo_reference_not_available")
            photo["lifecycle_state"] = "RESERVED"
            photo["application_id"] = application_id
            return True

    def finalize_photo_for_application(self, photo_object_id, application_id, participant_id):
        with self._lock:
            photo = self.photo_objects.get(photo_object_id)
            if not photo or photo["application_id"] != application_id:
                raise RepositoryConflict("photo_reservation_missing")
            photo.update({
                "lifecycle_state": "ATTACHED",
                "participant_id": participant_id,
            })
            participant = self.participants[participant_id]
            if not participant.get("current_photo_object_id"):
                participant["current_photo_object_id"] = photo_object_id
            participant["photo_required_blocked"] = False
            return True

    def replace_participant_photo(self, participant_id, photo_object_id, upload_context):
        """Switch current photo without changing any Application snapshot."""
        validate_photo_object_id(photo_object_id)
        with self._lock:
            participant = self.participants.get(participant_id)
            photo = self.photo_objects.get(photo_object_id)
            if not participant:
                return None
            if not photo or photo["owner_context_hash"] != self._context_hash(upload_context):
                raise RepositoryConflict("photo_reference_not_owned")
            if photo["lifecycle_state"] != "READY":
                raise RepositoryConflict("photo_reference_not_available")
            old_id = participant.get("current_photo_object_id")
            if old_id and old_id in self.photo_objects:
                self.photo_objects[old_id]["lifecycle_state"] = "DELETE_SCHEDULED"
            photo.update({"lifecycle_state": "ATTACHED", "participant_id": participant_id})
            participant["current_photo_object_id"] = photo_object_id
            participant["photo_required_blocked"] = False
            return {"participant_id": participant_id, "old_photo_object_id": old_id, "current_photo_object_id": photo_object_id}

    def delete_current_photo(self, participant_id):
        """Stop active photo use without deleting the Participant or Application."""
        with self._lock:
            participant = self.participants.get(participant_id)
            if not participant:
                return None
            photo_object_id = participant.get("current_photo_object_id")
            if photo_object_id and photo_object_id in self.photo_objects:
                self.photo_objects[photo_object_id].update({
                    "lifecycle_state": "DELETE_REQUESTED",
                    "deleted_at": "TEST-TIMESTAMP",
                })
            participant["current_photo_object_id"] = None
            participant["photo_required_blocked"] = participant.get("participant_status") != "Одобрен"
            return {"participant_id": participant_id, "photo_object_id": photo_object_id, "participation_deleted": False, "selection_blocked": participant["photo_required_blocked"]}

    def get_idempotency(self, key):
        return self.by_key.get(key)

    def resolve_phone(self, phone):
        participant_id = self.by_phone.get(normalize_phone(phone))
        if participant_id and participant_id not in self.participants:
            raise RepositoryConflict("phone_key_inconsistent")
        return participant_id

    def save(self, key, record):
        with self._lock:
            if key in self.by_key:
                return False
            phone = record["form"]["phone"]
            owner = self.by_phone.get(phone)
            if owner and owner not in self.participants:
                raise RepositoryConflict("phone_key_inconsistent")
            if owner in self.blocks:
                raise RepositoryUnavailable("processing_blocked")
            if owner is None:
                owner = record["participant_id"]
                if owner in self.participants:
                    raise RepositoryConflict("participant_id_conflict")
                form = record["form"]
                self.participants[owner] = {
                    "participant_id": owner, "environment": "TEST", "phone": phone,
                    "full_name": form["full_name"], "age": form["age"],
                    "gender": form["gender"], "city": form["city"],
                    "visit_krasnodar": form["visit_krasnodar"],
                    "telegram": form["profile_or_messenger_url"], "email": form["email"],
                    "profile_or_messenger_url": form["profile_or_messenger_url"],
                    "occupation": form["occupation"],
                    "preferred_contact": form["preferred_contact"],
                    "public_profile_url": form["public_profile_url"],
                    "participant_status": INITIAL_PARTICIPANT_STATUS, "lifecycle_status": "Новая заявка",
                    "owner": "", "priority": "", "next_action": "",
                    "next_contact_at": None, "decision": "", "internal_comment": "",
                    "processing_blocked": False, "processing_blocked_at": None,
                    "processing_block_reason": "", "processing_block_request_id": "",
                    "current_photo_object_id": None, "photo_required_blocked": False,
                }
                self.by_phone[phone] = owner
            record["participant_id"] = owner
            record["consent"]["participant_id"] = owner
            record["application_status"] = INITIAL_APPLICATION_STATUS
            record["decision"] = ""
            self.by_key[key] = deepcopy(record)
            self.audit.append({"request_id": record["request_id"], "application_id": record["application_id"], "participant_id": owner, "operation": "application_created", "status": "ok"})
            return True

    def applied_migrations(self):
        return tuple(sorted(self.migrations))

    def register_migration(self, migration_id):
        from .migration_ledger import validate_migration_id
        validate_migration_id(migration_id)
        with self._lock:
            if migration_id in self.migrations:
                return False
            self.migrations.add(migration_id)
            return True

    def list_admin_applications(self, filters=None, sort="submitted_at", order="desc"):
        filters = filters or {}
        rows = []
        for record in self.by_key.values():
            if record["environment"] != "TEST":
                continue
            participant, form = self.participants[record["participant_id"]], record["form"]
            row = {"application_id": record["application_id"], "participant_id": record["participant_id"], "submitted_at": record["submitted_at"], "full_name": form["full_name"], "age": form["age"], "city": form["city"], "phone": form["phone"], "telegram": form["profile_or_messenger_url"], "preferred_contact": form["preferred_contact"], "environment": "TEST", **{name: participant.get(name) for name in ("lifecycle_status", "owner", "priority", "next_action", "next_contact_at", "decision")}}
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
            applications.append({"application_id": record["application_id"], "submitted_at": record["submitted_at"], "form_version": record["consent"]["form_version"], "application_status": record.get("application_status", ""), "decision": record.get("decision", ""), "request_id": record["request_id"], "form": deepcopy(record["form"])})
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
        if not participant or participant.get("environment") != "TEST":
            return None
        result = deepcopy(participant)
        result["processing_state"] = "Заблокирована" if result.get("processing_blocked") else "Разрешена"
        return result

    def find_participant_by_phone(self, phone):
        participant_id = self.resolve_phone(phone)
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
        participant.update({"processing_blocked": True, "processing_state": "Заблокирована", "processing_blocked_at": "TEST-TIMESTAMP", "processing_block_reason": reason, "processing_block_request_id": request_id})
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
        photo_count = sum(1 for photo in self.photo_objects.values() if photo.get("participant_id") == participant_id)
        counts = {"participant": 1, "participant_phone_keys": phone_keys, "applications": len(application_ids), "consents": len(consent_ids), "technical_logs": len(records), "audit_log": audit_count, "photo_objects": photo_count}
        inventory = {name: {"count": count, **DESTRUCTION_CLASSIFICATION[name]} for name, count in counts.items() if name != "photo_objects"}
        inventory["photo_objects"] = {"count": photo_count, **PHOTO_DESTRUCTION_CLASSIFICATION}
        return {"participant_id": participant_id, "dry_run": True, "delete_performed": False, "records": inventory, "application_ids": application_ids, "consent_ids": consent_ids}

