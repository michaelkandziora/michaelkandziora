"""Small GitHub REST/GraphQL client. No third-party services or private exports."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

class APIError(RuntimeError):
    """A request failed or its data cannot be considered complete."""

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> None:
        raise APIError('Unexpected API redirect; credentials were not forwarded.')

class GitHubClient:
    def __init__(self, token: str | None = None, timeout: int = 25):
        self.token = (token or '').strip()
        self.timeout = timeout
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, method: str, path: str, data: dict[str, Any] | None = None) -> Any:
        if not path.startswith('/') or path.startswith('//'):
            raise APIError('Only relative GitHub API paths are accepted.')
        headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'ascii-profile-readme/1.0',
                   'X-GitHub-Api-Version': '2026-03-10'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        payload = None if data is None else json.dumps(data).encode('utf-8')
        if payload is not None:
            headers['Content-Type'] = 'application/json'
        for attempt in range(3):
            try:
                req = urllib.request.Request('https://api.github.com' + path, data=payload,
                                             headers=headers, method=method)
                with self.opener.open(req, timeout=self.timeout) as response:
                    body = response.read(16 * 1024 * 1024 + 1)
                    if len(body) > 16 * 1024 * 1024:
                        raise APIError('GitHub response exceeded the safe size limit.')
                    return json.loads(body)
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                    # Bounded retries; never sleep for an entire exhausted rate-limit window.
                    time.sleep(2 ** attempt)
                    continue
                raise APIError(f'GitHub HTTP {exc.code}; check token permissions, rate limits and repository access.') from None
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise APIError('GitHub network request failed after three attempts.') from exc
            except (json.JSONDecodeError, UnicodeError) as exc:
                raise APIError('GitHub returned invalid JSON.') from exc
        raise APIError('GitHub request failed.')


def nonnegative(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise APIError('GitHub returned a missing or invalid count.')
    return value


def list_repositories(client: Any, username: str) -> list[dict[str, Any]]:
    result = []
    for page in range(1, 1001):
        query = urllib.parse.urlencode({'type':'owner', 'sort':'full_name', 'per_page':100, 'page':page})
        data = client.request('GET', f'/users/{username}/repos?{query}')
        if not isinstance(data, list):
            raise APIError('Expected a repository list.')
        result.extend(data)
        if len(data) < 100:
            return result
    raise APIError('Repository pagination limit reached; refusing a partial total.')


def repository_totals(repositories: list[dict[str, Any]], username: str,
                      exclude_forks: bool) -> dict[str, int]:
    selected = [r for r in repositories
                if r.get('private') is False
                and r.get('owner', {}).get('login', '').lower() == username.lower()
                and (not exclude_forks or r.get('fork') is False)]
    return {'repos': len(selected), 'stars': sum(nonnegative(r['stargazers_count']) for r in selected)}


def pull_request_count(client: Any, username: str) -> int:
    query = urllib.parse.urlencode({'q':f'type:pr author:{username} is:public', 'per_page':1})
    result = client.request('GET', '/search/issues?' + query)
    if result.get('incomplete_results') is not False:
        raise APIError('GitHub search was incomplete; refusing a partial PR count.')
    return nonnegative(result.get('total_count'))


COMMIT_QUERY = '''query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalRepositoriesWithContributedCommits
      commitContributionsByRepository(maxRepositories: 100) {
        repository { isPrivate }
        contributions { totalCount }
      }
    }
  }
}'''


def commit_stats(client: Any, username: str, days: int = 365,
                 now: datetime | None = None) -> dict[str, int]:
    if not client.token:
        raise APIError('GraphQL requires GH_TOKEN or GITHUB_TOKEN; the workflow supplies GITHUB_TOKEN automatically.')
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('now must include a timezone.')
    end = now.astimezone(timezone.utc).replace(microsecond=0)
    start = end - timedelta(days=days)
    iso = lambda value: value.isoformat().replace('+00:00', 'Z')
    result = client.request('POST', '/graphql', {'query': COMMIT_QUERY,
                'variables': {'login':username, 'from':iso(start), 'to':iso(end)}})
    if result.get('errors'):
        raise APIError('GitHub GraphQL returned errors; check token access. No partial results were used.')
    try:
        collection = result['data']['user']['contributionsCollection']
        groups = collection['commitContributionsByRepository']
        expected = nonnegative(collection['totalRepositoriesWithContributedCommits'])
        if expected != len(groups):
            raise APIError('Commit repository list is incomplete (maximum 100); refusing a partial total.')
        public = [g for g in groups if g['repository']['isPrivate'] is False]
        return {'commits_365d': sum(nonnegative(g['contributions']['totalCount']) for g in public),
                'contributed_repos_365d': len(public)}
    except (KeyError, TypeError) as exc:
        raise APIError('GitHub returned an invalid contribution collection.') from exc


def collect(client: Any, username: str, exclude_forks: bool = True,
            days: int = 365) -> tuple[dict[str, int], dict[str, str], list[dict[str, Any]] | None]:
    values, errors = {}, {}
    repositories = None
    def attempt(keys: tuple[str, ...], operation: Any) -> None:
        try:
            values.update(operation())
        except (APIError, KeyError, TypeError, ValueError) as exc:
            message = str(exc) if isinstance(exc, APIError) else 'Unexpected GitHub response shape.'
            errors.update({key:message for key in keys})
    def profile() -> dict[str, int]:
        data = client.request('GET', f'/users/{username}')
        return {key:nonnegative(data[key]) for key in ('followers','following','public_gists')}
    def repos() -> dict[str, int]:
        nonlocal repositories
        repositories = list_repositories(client, username)
        return repository_totals(repositories, username, exclude_forks)
    attempt(('followers','following','public_gists'), profile)
    attempt(('repos','stars'), repos)
    attempt(('pull_requests',), lambda: {'pull_requests':pull_request_count(client, username)})
    attempt(('commits_365d','contributed_repos_365d'), lambda: commit_stats(client, username, days))
    return values, errors, repositories
