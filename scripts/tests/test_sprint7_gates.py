"""Gate negative tests use temporary artifacts and never touch a live server."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sprint7_smoke import local_base, NoRedirect
from sprint7_release_evidence import REQUIRED, validate


class ReleaseEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root/'proof.txt').write_text('Synthetic gate unit fixture, not acceptance evidence')
        digest = hashlib.sha256((self.root/'proof.txt').read_bytes()).hexdigest()
        self.data = {'commit':'synthetic-sha','open_p0_p1':0,'gates':{name:{
            'status':'PASS','reviewer':'Unit fixture','reviewed_at':'2026-10-29',
            'artifact':'proof.txt','sha256':digest} for name in REQUIRED}}

    def errors(self):
        return validate(self.data, commit='synthetic-sha', root=self.root)

    def test_complete_record_matches_artifacts(self):
        self.assertEqual(self.errors(), [])

    def test_missing_or_pending_manual_gates_block(self):
        for name in REQUIRED:
            with self.subTest(name=name):
                self.data['gates'][name]['status'] = 'PENDING'
                self.assertTrue(self.errors())
                self.data['gates'][name]['status'] = 'PASS'

    def test_stale_commit_blocks(self):
        self.data['commit'] = 'older-sha'
        self.assertTrue(self.errors())

    def test_invalid_review_date_blocks(self):
        self.data['gates']['native_ios']['reviewed_at'] = 'not reviewed'
        self.assertTrue(self.errors())

    def test_null_reviewer_is_not_a_signoff(self):
        self.data['gates']['native_ios']['reviewer'] = None
        self.assertTrue(self.errors())

    def test_open_or_unreviewed_issues_block(self):
        for value in (None, 1, '0', False):
            self.data['open_p0_p1'] = value
            self.assertTrue(self.errors())

    def test_missing_or_modified_artifact_blocks(self):
        (self.root/'proof.txt').write_text('Changed')
        self.assertTrue(self.errors())
        (self.root/'proof.txt').unlink()
        self.assertTrue(self.errors())

    def test_path_escape_blocks(self):
        self.data['gates']['native_ios']['artifact'] = '../escape.txt'
        self.assertTrue(self.errors())


class SmokeBoundaryTests(unittest.TestCase):
    def test_only_loopback_origins(self):
        for origin in ('http://127.0.0.1:8000','http://localhost:8000/', 'http://[::1]:8000'):
            self.assertEqual(local_base(origin), origin.rstrip('/'))
        for origin in ('http://localhost:8000@evil.test','http://127.0.0.1.evil.test:8000',
                       'http://school.test:8000','http://localhost:8000/path',
                       'http://localhost:8000?x=y','http://localhost:8000#x','http://localhost'):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                local_base(origin)

    def test_redirects_never_forward_demo_credentials(self):
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,'redirect',{},'https://example.test'))
