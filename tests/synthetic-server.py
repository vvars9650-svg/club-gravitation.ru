"""Local-only synthetic E2E; real handler/codec, in-memory repository/storage."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from backend.v5.handler import handler
from backend.v5.repository import FakeRepository
from backend.v5.photo_upload_service import PhotoUploadService
from backend.v5.image_codec import PillowPhotoCodec
from backend.v5.tests.test_photo_upload_pipeline import FakeStorage

repo = FakeRepository()
storage = FakeStorage()


class Presigner:
    def presign_put(self, bucket, key, expires_in):
        return 'http://127.0.0.1:4180/upload/' + key


photos = PhotoUploadService(repository=repo, storage=storage, presigner=Presigner(), codec=PillowPhotoCodec(), bucket='synthetic-private')


class Server(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_PUT(self):
        storage.objects[self.path.removeprefix('/upload/')] = self.rfile.read(int(self.headers['Content-Length']))
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        event = {'httpMethod':'POST', 'path':self.path, 'headers':dict(self.headers), 'body':self.rfile.read(int(self.headers['Content-Length'])).decode()}
        result = handler(event, repo=repo, photo_service=photos)
        self.send_response(result['statusCode'])
        self.send_header('Content-Type','application/json')
        self.end_headers()
        self.wfile.write(result['body'].encode())


ThreadingHTTPServer(('127.0.0.1',4180),Server).serve_forever()
