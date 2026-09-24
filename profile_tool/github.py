"""Small GitHub REST/GraphQL client. No third-party services or private repository exports."""
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

    def _request(self, method: str, path: str, data: dict[str, Any] | None,
                 authenticated: bool) -> Any:
        if not path.startswith('/') or path.startswith('//'):
            raise APIError('Only relative GitHub API paths are accepted.')
        headers = {'Accept': 'application/vnd.github+json',
                   'User-Agent': 'ascii-profile-readme/1.0',
                   'X-GitHub-Api-Version': '2026-03-10'}
        if authenticated and self.token:
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
                    time.sleep(2 ** attempt)
                    continue
                raise APIError(
                    f'GitHub HTTP {exc.code}; check token permissions, rate limits and repository access.'
                ) from None
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise APIError('GitHub network request failed after three attempts.') from exc
            except (json.JSONDecodeError, UnicodeError) as exc:
                raise APIError('GitHub returned invalid JSON.') from exc
        raise APIError('GitHub request failed.')

    def request(self, method: str, path: str, data: dict[str, Any] | None = None) -> Any:
        return self._request(method, path, data, authenticated=True)

    def request_public(self, method: str, path: str,
                       data: dict[str, Any] | None = None) -> Any:
        """Make a deliberately unauthenticated request so private resources cannot affect totals."""
        return self._request(method, path, data, authenticated=False)


def public_request(client: Any, method: str, path: str,
                   data: dict[str, Any] | None = None) -> Any:
    request = getattr(client, 'request_public', None)
    return request(method, path, data) if request else client.request(method, path, data)


def nonnegative(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise APIError('GitHub returned a missing or invalid count.')
    return value


def owner_profile(client: Any, username: str) -> dict[str, Any]:
    """Require a user token for the configured profile owner, never a repository installation token."""
    if not getattr(client, 'token', ''):
        raise APIError(
            f'PROFILE_STATS_TOKEN is required for owner-only profile metrics for @{username}.'
        )
    try:
        data = client.request('GET', '/user')
    except APIError as exc:
        raise APIError(
            f'PROFILE_STATS_TOKEN must authenticate as @{username}; the repository GITHUB_TOKEN is not sufficient.'
        ) from exc
    login = data.get('login') if isinstance(data, dict) else None
    if not isinstance(login, str) or login.lower() != username.lower():
        shown = f'@{login}' if isinstance(login, str) and login else 'another identity'
        raise APIError(
            f'PROFILE_STATS_TOKEN authenticates as {shown}, expected @{username}.'
        )
    return data


def list_repositories(client: Any, username: str) -> list[dict[str, Any]]:
    result = []
    for page in range(1, 1001):
        query = urllib.parse.urlencode(
            {'type': 'owner', 'sort': 'full_name', 'per_page': 100, 'page': page}
        )
        data = public_request(client, 'GET', f'/users/{username}/repos?{query}')
        if not isinstance(data, list):
            raise APIError('Expected a repository list.')
        result.extend(data)
        if len(data) < 100:
            return result
    raise APIError('Repository pagination limit reached; refusing a partial total.')


def repository_totals(repositories: list[dict[str, Any]], username: str,
                      exclude_forks: bool) -> dict[str, int]:
    selected = [
        r for r in repositories
        if r.get('private') is False
        and r.get('owner', {}).get('login', '').lower() == username.lower()
        and (not exclude_forks or r.get('fork') is False)
    ]
    stars_received = sum(nonnegative(r['stargazers_count']) for r in selected)
    return {'repos': len(selected), 'stars': stars_received, 'stars_received': stars_received}


def starred_repository_count(client: Any, username: str) -> int:
    """Count public repositories starred by the owner; private starred repositories stay excluded."""
    total = 0
    for page in range(1, 1001):
        query = urllib.parse.urlencode({'per_page': 100, 'page': page})
        data = client.request('GET', f'/users/{username}/starred?{query}')
        if not isinstance(data, list):
            raise APIError('Expected a starred repository list.')
        total += sum(1 for repo in data if repo.get('private') is False)
        if len(data) < 100:
            return total
    raise APIError('Starred repository pagination limit reached; refusing a partial total.')


def pull_request_count(client: Any, username: str) -> int:
    query = urllib.parse.urlencode({'q': f'type:pr author:{username}', 'per_page': 1})
    result = public_request(client, 'GET', '/search/issues?' + query)
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
    if not getattr(client, 'token', ''):
        raise APIError('PROFILE_STATS_TOKEN is required for contribution metrics.')
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('now must include a timezone.')
    end = now.astimezone(timezone.utc).replace(microsecond=0)
    start = end - timedelta(days=days)
    iso = lambda value: value.isoformat().replace('+00:00', 'Z')
    result = client.request('POST', '/graphql', {
        'query': COMMIT_QUERY,
        'variables': {'login': username, 'from': iso(start), 'to': iso(end)}
    })
    if result.get('errors'):
        raise APIError('GitHub GraphQL returned errors; check PROFILE_STATS_TOKEN access.')
    try:
        collection = result['data']['user']['contributionsCollection']
        groups = collection['commitContributionsByRepository']
        expected = nonnegative(collection['totalRepositoriesWithContributedCommits'])
        if expected != len(groups):
            raise APIError(
                'Commit repository list is incomplete (maximum 100); refusing a partial total.'
            )
        public = [g for g in groups if g['repository']['isPrivate'] is False]
        return {
            'commits_365d': sum(nonnegative(g['contributions']['totalCount']) for g in public),
            'contributed_repos_365d': len(public)
        }
    except (KeyError, TypeError) as exc:
        raise APIError('GitHub returned an invalid contribution collection.') from exc


def collect(client: Any, username: str, exclude_forks: bool = True,
            days: int = 365) -> tuple[dict[str, int], dict[str, str],
                                     list[dict[str, Any]] | None]:
    values: dict[str, int] = {}
    errors: dict[str, str] = {}
    repositories = None

    def attempt(keys: tuple[str, ...], operation: Any) -> None:
        try:
            values.update(operation())
        except (APIError, KeyError, TypeError, ValueError) as exc:
            message = str(exc) if isinstance(exc, APIError) else 'Unexpected GitHub response shape.'
            errors.update({key: message for key in keys})

    def public_profile() -> dict[str, int]:
        data = public_request(client, 'GET', f'/users/{username}')
        return {'public_gists': nonnegative(data['public_gists'])}

    def repos() -> dict[str, int]:
        nonlocal repositories
        repositories = list_repositories(client, username)
        return repository_totals(repositories, username, exclude_forks)

    attempt(('public_gists',), public_profile)
    attempt(('repos', 'stars', 'stars_received'), repos)
    attempt(('pull_requests',), lambda: {'pull_requests': pull_request_count(client, username)})

    try:
        owner = owner_profile(client, username)
    except (APIError, KeyError, TypeError, ValueError) as exc:
        message = str(exc) if isinstance(exc, APIError) else 'Unexpected GitHub owner profile response.'
        errors.update({
            key: message for key in
            ('followers', 'following', 'starred', 'commits_365d', 'contributed_repos_365d')
        })
    else:
        try:
            values.update({
                'followers': nonnegative(owner['followers']),
                'following': nonnegative(owner['following'])
            })
        except (APIError, KeyError, TypeError, ValueError) as exc:
            message = str(exc) if isinstance(exc, APIError) else 'Unexpected GitHub owner profile response.'
            errors.update({key: message for key in ('followers', 'following')})
        attempt(('starred',), lambda: {'starred': starred_repository_count(client, username)})
        attempt(
            ('commits_365d', 'contributed_repos_365d'),
            lambda: commit_stats(client, username, days)
        )

    return values, errors, repositories
