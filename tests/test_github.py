import unittest
from datetime import datetime, timezone
from profile_tool import github, stats

class FakeClient:
    def __init__(self, replies, token='fake-token'):
        self.replies=list(replies);self.calls=[];self.token=token
    def request(self,method,path,data=None):
        self.calls.append((method,path,data))
        value=self.replies.pop(0)
        if isinstance(value,Exception):raise value
        return value

class GithubTests(unittest.TestCase):
    def test_repo_pagination(self):
        c=FakeClient([[{'id':i} for i in range(100)],[{'id':100}]])
        self.assertEqual(len(github.list_repositories(c,'alice')),101)
        self.assertIn('page=2',c.calls[-1][1])

    def test_public_commit_filter_and_period(self):
        c=FakeClient([{'data':{'user':{'contributionsCollection':{
            'totalRepositoriesWithContributedCommits':2,
            'commitContributionsByRepository':[
                {'repository':{'isPrivate':False},'contributions':{'totalCount':12}},
                {'repository':{'isPrivate':True},'contributions':{'totalCount':999}}
            ]}}}}])
        values=github.commit_stats(c,'alice',365,datetime(2026,9,8,tzinfo=timezone.utc))
        self.assertEqual(values,{'commits_365d':12,'contributed_repos_365d':1})
        self.assertEqual(c.calls[0][2]['variables']['from'],'2025-09-08T00:00:00Z')

    def test_truncated_contributions_rejected(self):
        c=FakeClient([{'data':{'user':{'contributionsCollection':{
            'totalRepositoriesWithContributedCommits':101,'commitContributionsByRepository':[]}}}}])
        with self.assertRaises(github.APIError):github.commit_stats(c,'alice',365)

    def test_graphql_errors_rejected(self):
        c=FakeClient([{'errors':[{'message':'no access'}]}])
        with self.assertRaises(github.APIError):github.commit_stats(c,'alice',365)

    def test_incomplete_search_rejected(self):
        c=FakeClient([{'incomplete_results':True,'total_count':5}])
        with self.assertRaises(github.APIError):github.pull_request_count(c,'alice')
        self.assertIn('is%3Apublic',c.calls[0][1])

    def test_repo_filter_owner_private_and_forks(self):
        rows=[{'owner':{'login':'Alice'},'private':False,'fork':False,'stargazers_count':7},
              {'owner':{'login':'alice'},'private':True,'fork':False,'stargazers_count':900},
              {'owner':{'login':'alice'},'private':False,'fork':True,'stargazers_count':100},
              {'owner':{'login':'other'},'private':False,'fork':False,'stargazers_count':100}]
        self.assertEqual(github.repository_totals(rows,'alice',True),{'repos':1,'stars':7})

    def test_failed_update_keeps_value_marked_stale(self):
        old={'username':'alice','metrics':{'stars':{'value':12,'status':'ok','updated_at':'2026-09-01'}}}
        new=stats.merge_metrics(old,{}, {'stars':'API unavailable'},set(),'alice','2026-09-08')
        self.assertEqual(new['metrics']['stars']['value'],12)
        self.assertEqual(new['metrics']['stars']['status'],'stale')
        self.assertEqual(new['metrics']['stars']['updated_at'],'2026-09-01')

    def test_disabling_metric_does_not_show_old_scope(self):
        old={'username':'alice','metrics':{'loc':{'value':100,'status':'ok'}}}
        new=stats.merge_metrics(old,{}, {},{'loc'},'alice','2026-09-08')
        self.assertIsNone(new['metrics']['loc']['value'])
        self.assertEqual(new['metrics']['loc']['status'],'disabled')

    def test_zero_success_is_zero(self):
        new=stats.merge_metrics({}, {'stars':0}, {},set(),'alice','2026-09-08')
        self.assertEqual(new['metrics']['stars']['value'],0)
        self.assertEqual(new['metrics']['stars']['status'],'ok')
