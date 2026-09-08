import unittest
import urllib.error
from unittest.mock import patch
from profile_tool import github

class Response:
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,*args):return b'{"followers": 3}'
class Opener:
    def __init__(self,failures):self.failures=failures;self.requests=[]
    def open(self,request,timeout=None):
        self.requests.append(request)
        if self.failures:
            code=self.failures.pop(0)
            raise urllib.error.HTTPError(request.full_url,code,'failed',{},None)
        return Response()
class TransportTests(unittest.TestCase):
    def test_authorization_header_and_version(self):
        c=github.GitHubClient('SECRET_TEST_SENTINEL');c.opener=Opener([])
        self.assertEqual(c.request('GET','/users/octocat')['followers'],3)
        r=c.opener.requests[0]
        self.assertEqual(r.get_header('Authorization'),'Bearer SECRET_TEST_SENTINEL')
        self.assertEqual(r.get_header('X-github-api-version'),'2026-03-10')
    def test_401_is_not_retried_or_secret_logged(self):
        c=github.GitHubClient('SECRET_TEST_SENTINEL');c.opener=Opener([401])
        with self.assertRaises(github.APIError) as cm:c.request('GET','/users/octocat')
        self.assertNotIn('SECRET_TEST_SENTINEL',str(cm.exception))
        self.assertEqual(len(c.opener.requests),1)
    @patch('profile_tool.github.time.sleep')
    def test_transient_error_retries_and_recovers(self,sleep):
        c=github.GitHubClient();c.opener=Opener([503,502])
        self.assertEqual(c.request('GET','/users/octocat'),{'followers':3})
        self.assertEqual(len(c.opener.requests),3)
    def test_external_urls_rejected(self):
        c=github.GitHubClient('secret')
        for path in ('https://evil.invalid','//evil.invalid'):
            with self.assertRaises(github.APIError):c.request('GET',path)
