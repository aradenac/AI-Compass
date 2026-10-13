#!/usr/bin/env python3
"""FUT-19: unit tests for the resumable archive download client (no network)."""
import hashlib
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts import archive_download  # noqa: E402

BODY = b"PK\x03\x04 native archive body for client tests\n" * 500
DIGEST = hashlib.sha256(BODY).hexdigest()


class _Response(io.BytesIO):
    def __init__(self, payload, status=200, etag=DIGEST):
        super().__init__(payload)
        self.status = status
        self.headers = {"ETag": '"%s"' % etag}


class ClientTests(unittest.TestCase):
    def test_full_download_verifies_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "a.zip")
            with mock.patch("urllib.request.urlopen", return_value=_Response(BODY)):
                archive_download.download("http://x", "agr-1", out, "tok")
            self.assertEqual(open(out, "rb").read(), BODY)

    def test_resume_sends_range_and_reassembles(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "a.zip")
            head = BODY[:100]
            open(out, "wb").write(head)
            seen = {}

            def fake(request, timeout=None):
                seen["range"] = request.headers.get("Range")
                return _Response(BODY[100:], status=206)

            with mock.patch("urllib.request.urlopen", side_effect=fake):
                archive_download.download("http://x", "agr-1", out, "tok")
            self.assertEqual(seen["range"], "bytes=100-")
            self.assertEqual(open(out, "rb").read(), BODY)

    def test_corrupt_bytes_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "a.zip")
            with mock.patch("urllib.request.urlopen",
                            return_value=_Response(BODY, etag="0" * 64)):
                with self.assertRaises(SystemExit):
                    archive_download.download("http://x", "agr-1", out, "tok")

    def test_main_requires_token_in_environment(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                archive_download.main(["--base-url", "http://x", "--job", "j",
                                       "--output", "/tmp/x.zip"])


if __name__ == "__main__":
    unittest.main()
