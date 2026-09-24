import unittest
from datetime import datetime, timezone
from profile_tool import github, stats


class FakeClient:
    def __init__(self, replies, token='fake-token'):
        self.replies = list(replies)
        self.calls = []
        self.token = token

    def request(self, method, path, data=None):
        self.calls.append(('auth', method, path, data))
        value = self.replies.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def request_public(self, method, path, data=None):
        self.calls.append(('public', method, path, data))
        value = self.replies.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


class GithubTests(unittest.TestCase):
    def test_repo_pagination_is_deliberately_public(self):
        c = FakeClient([[{'id': i} for i in range(100)], [{'id': 100}]])
        self.assertEqual(len(github.list_repositories(c, 'alice')), 101)
        self.assertEqual(c.calls[0][0], 'public')
        self.assertIn('page=2', c.calls[-1][2])

    def test_owner_token_must_match_profile(self):
        c = FakeClient([{'login': 'mallory'}])
        with self.assertRaises(github.APIError):
            github.owner_profile(c, 'alice')

    def test_owner_token_is_required(self):
        c = FakeClient([], token='')
        with self.assertRaises(github.APIError):
            github.owner_profile(c, 'alice')

    def test_starred_count_filters_private_repositories(self):
        c = FakeClient([[{'private': False}, {'private': True}, {'private': False}]])
        self.assertEqual(github.starred_repository_count(c, 'alice'), 2)

    def test_public_commit_filter_and_period(self):
        c = FakeClient([{'data': {'user': {'contributionsCollection': {
            'totalRepositoriesWithContributedCommits': 2,
            'commitContributionsByRepository': [
                {'repository': {'isPrivate': False}, 'contributions': {'totalCount': 12}},
                {'repository': {'isPrivate': True}, 'contributions': {'totalCount': 999}}
            ]
        }}}}])
        values = github.commit_stats(c, 'alice', 365, datetime(2026, 9, 8, tzinfo=timezone.utc))
        self.assertEqual(values, {'commits_365d': 12, 'contributed_repos_365d': 1})
        self.assertEqual(c.calls[0][3]['variables']['from'], '2025-09-08T00:00:00Z')

    def test_truncated_contributions_rejected(self):
        c = FakeClient([{'data': {'user': {'contributionsCollection': {
            'totalRepositoriesWithContributedCommits': 101,
            'commitContributionsByRepository': []
        }}}}])
        with self.assertRaises(github.APIError):
            github.commit_stats(c, 'alice', 365)

    def test_graphql_errors_rejected(self):
        c = FakeClient([{'errors': [{'message': 'no access'}]}])
        with self.assertRaises(github.APIError):
            github.commit_stats(c, 'alice', 365)

    def test_pr_search_is_public_and_has_no_invalid_visibility_qualifier(self):
        c = FakeClient([{'incomplete_results': False, 'total_count': 5}])
        self.assertEqual(github.pull_request_count(c, 'alice'), 5)
        self.assertEqual(c.calls[0][0], 'public')
        self.assertNotIn('is%3Apublic', c.calls[0][2])

    def test_incomplete_search_rejected(self):
        c = FakeClient([{'incomplete_results': True, 'total_count': 5}])
        with self.assertRaises(github.APIError):
            github.pull_request_count(c, 'alice')

    def test_repo_filter_owner_private_and_forks(self):
        rows = [
            {'owner': {'login': 'Alice'}, 'private': False, 'fork': False, 'stargazers_count': 7},
            {'owner': {'login': 'alice'}, 'private': True, 'fork': False, 'stargazers_count': 900},
            {'owner': {'login': 'alice'}, 'private': False, 'fork': True, 'stargazers_count': 100},
            {'owner': {'login': 'other'}, 'private': False, 'fork': False, 'stargazers_count': 100}
        ]
        self.assertEqual(
            github.repository_totals(rows, 'alice', True),
            {'repos': 1, 'stars': 7, 'stars_received': 7}
        )

    def test_legacy_false_zero_is_invalidated(self):
        old = {'username': 'alice', 'metrics': {'followers': {'value': 0, 'status': 'ok'}}}
        self.assertNotIn('followers', stats.migrate_cache(old)['metrics'])

    def test_failed_update_keeps_verified_value_marked_stale(self):
        old = {
            'collector_version': stats.COLLECTOR_VERSION,
            'username': 'alice',
            'metrics': {'starred': {'value': 12, 'status': 'ok', 'updated_at': '2026-09-01'}}
        }
        new = stats.merge_metrics(old, {}, {'starred': 'API unavailable'}, set(), 'alice', '2026-09-08')
        self.assertEqual(new['metrics']['starred']['value'], 12)
        self.assertEqual(new['metrics']['starred']['status'], 'stale')

    def test_zero_success_is_zero(self):
        new = stats.merge_metrics({}, {'stars_received': 0}, {}, set(), 'alice', '2026-09-08')
        self.assertEqual(new['metrics']['stars_received']['value'], 0)
        self.assertEqual(new['metrics']['stars_received']['status'], 'ok')
