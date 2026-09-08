import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from profile_tool import github, render, stats

ROOT=Path(__file__).resolve().parents[1]
class FakeClient:
    token='not-a-real-token'
    def __init__(self,stars=7,graph_error=False):self.stars=stars;self.graph_error=graph_error
    def request(self,method,path,data=None):
        if path=='/users/michaelkandziora':return {'followers':3,'following':2,'public_gists':0}
        if path.startswith('/users/michaelkandziora/repos?'):
            return [{'full_name':'michaelkandziora/demo','owner':{'login':'michaelkandziora'},
                     'private':False,'fork':False,'archived':False,'size':5,'stargazers_count':self.stars}]
        if path.startswith('/search/issues?'):return {'total_count':4,'incomplete_results':False}
        if path=='/graphql':
            if self.graph_error:return {'errors':[{'message':'denied'}]}
            return {'data':{'user':{'contributionsCollection':{'totalRepositoriesWithContributedCommits':1,
                    'commitContributionsByRepository':[{'repository':{'isPrivate':False},'contributions':{'totalCount':23}}]}}}}
        raise AssertionError(path)

class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'repo';shutil.copytree(ROOT/'tests/fixtures',self.root)
        render.write_generated(self.root)
    def test_complete_offline_update_twice(self):
        original=(self.root/'assets/portrait.txt').read_bytes()
        _,errors=stats.update(self.root,strict=True,client=FakeClient())
        self.assertEqual(errors,{})
        first=(self.root/'README.template.md').read_bytes()
        stats.update(self.root,strict=True,client=FakeClient(stars=9))
        cache=json.loads((self.root/'.profile/stats.json').read_text())
        self.assertEqual(cache['metrics']['stars']['value'],9)
        self.assertEqual(cache['metrics']['commits_365d']['value'],23)
        self.assertTrue(render.check_generated(self.root))
        self.assertEqual(first,(self.root/'README.template.md').read_bytes())
        self.assertEqual(original,(self.root/'assets/portrait.txt').read_bytes())
    def test_same_day_update_is_idempotent(self):
        stats.update(self.root,strict=True,client=FakeClient())
        changes,errors=stats.update(self.root,strict=True,client=FakeClient())
        self.assertEqual(changes,[]);self.assertEqual(errors,{})
    def test_strict_failure_does_not_write_any_file(self):
        paths=['.profile/stats.json','README.md','README.template.md','profile.json']
        before={name:(self.root/name).read_bytes() for name in paths}
        with self.assertRaises(github.APIError):stats.update(self.root,strict=True,client=FakeClient(graph_error=True))
        self.assertEqual(before,{name:(self.root/name).read_bytes() for name in paths})
    def test_partial_failure_marks_last_value(self):
        stats.update(self.root,client=FakeClient())
        _,errors=stats.update(self.root,client=FakeClient(stars=11,graph_error=True))
        self.assertIn('commits_365d',errors)
        self.assertIn('23*',(self.root/'README.md').read_text())
        self.assertEqual(json.loads((self.root/'.profile/stats.json').read_text())['metrics']['stars']['value'],11)
    def test_code_scope_change_invalidates_old_values(self):
        config=json.loads((self.root/'profile.json').read_text());config['code']['enabled']=True
        oldconfig=copy.deepcopy(config);oldconfig['code']['repositories']=['michaelkandziora/old']
        cache={'username':'michaelkandziora','settings':{'code':oldconfig['code']},'metrics':{'loc':{'value':999,'status':'ok'}}}
        self.assertEqual(render.resolve_template('{{stats.loc}}',config,cache),'n/a')
