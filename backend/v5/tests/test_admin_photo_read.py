import unittest
from unittest.mock import patch
from backend.v5.factory import runtime_photo_reader
from backend.v5.repository import FakeRepository
from backend.v5.service import submit
from backend.v5.handler import handler
from backend.v5.tests.test_v5 import payload_with_photo
from backend.v5.tests.test_form_2_3 import SHORT


class AdminPhotoTests(unittest.TestCase):
    def test_only_attached_application_photo_gets_short_get_url(self):
        repo=FakeRepository()
        payload=payload_with_photo(repo,'photo-card',SHORT)
        record,_=submit(payload,'photo-card',repo,'synthetic')
        with patch.dict('os.environ',{'V5_TEST_PHOTO_BUCKET':'synthetic-private'}), patch('backend.v5.object_storage.runtime_iam_token',return_value='synthetic-token'), patch('backend.v5.object_storage.YandexPresignClient') as client:
            client.return_value.presign_get.return_value='https://storage.yandexcloud.net/synthetic-private/opaque?signed'
            reader=runtime_photo_reader(None,repo)
            application={'application_id':record['application_id'],'form':record['form']}
            photo=reader(application)
            self.assertEqual(photo['expires_in'],180)
            self.assertEqual(client.return_value.presign_get.call_args.args[-1],180)
            self.assertIsNone(reader({**application,'application_id':'APP-OTHER'}))
            repo.photo_objects[payload['photo_object_id']]['lifecycle_state']='DESTROYED'
            self.assertIsNone(reader(application))

    def test_unauthenticated_photo_request_never_creates_reader(self):
        with patch('backend.v5.handler.runtime_photo_reader') as reader:
            result=handler({'httpMethod':'GET','path':'/admin/applications/APP-X','queryStringParameters':{'include_photo':'true'}},repo=FakeRepository())
            self.assertEqual(result['statusCode'],401)
            reader.assert_not_called()
