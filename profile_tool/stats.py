"""Refresh typed metrics and keep last-good values explicitly marked stale."""
from __future__ import annotations

import copy
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from . import github
from .code_stats import scan_code
from .model import METRICS, load_cache, load_config, write_json
from .render import effective_cache, generate
from .model import atomic_write


def merge_metrics(old: dict[str, Any], values: dict[str, int], errors: dict[str, str],
                  disabled: set[str], username: str, now: str) -> dict[str, Any]:
    if old.get('username') and old['username'].lower() != username.lower():
        raise ValueError('Stats cache username mismatch.')
    result = copy.deepcopy(old)
    result.update({'schema_version':1, 'username':username, 'last_attempt':now})
    metrics = result.setdefault('metrics', {})
    for key, value in values.items():
        if key not in METRICS or type(value) is not int or value < 0:
            raise ValueError('Invalid collected statistic.')
        metrics[key] = {'value':value, 'status':'ok', 'updated_at':now}
    for key, message in errors.items():
        previous = metrics.get(key, {})
        has_value = previous.get('value') is not None
        metrics[key] = {'value':previous.get('value'), 'status':'stale' if has_value else 'missing',
                        'updated_at':previous.get('updated_at'), 'error':message}
    for key in disabled:
        metrics[key] = {'value':None, 'status':'disabled', 'updated_at':None}
    return result


def update(root: Path, strict: bool = False, client: Any = None) -> tuple[list[str], dict[str, str]]:
    config = load_config(root)
    old = effective_cache(config, load_cache(root))
    # Validate both generated documents before making any network requests or writes.
    generate(root, config, old)
    client = client or github.GitHubClient(os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN'))
    values, errors, repositories = github.collect(client, config['username'],
                        config['stats']['exclude_forks'], config['stats']['days'])
    disabled = set()
    if config['code']['enabled']:
        try:
            if repositories is None:
                raise ValueError('Code scan needs a complete public repository listing.')
            values.update(scan_code(repositories, config['code'], config['username']))
        except (ValueError, OSError) as exc:
            errors.update({key:str(exc) for key in ('loc','added','removed')})
    else:
        disabled.update(('loc','added','removed'))
    if strict and errors:
        raise github.APIError('Strict refresh failed; files were not changed. ' + '; '.join(sorted(set(errors.values()))))
    if not values:
        raise github.APIError('No metrics could be refreshed; files were not changed. Check connection and authentication.')
    now = datetime.now(timezone.utc).date().isoformat()
    cache = merge_metrics(old, values, errors, disabled, config['username'], now)
    cache['settings'] = {'stats':config['stats'], 'code':config['code']}
    template, readme = generate(root, config, cache)
    changed = []
    if write_json(root/'.profile/stats.json', cache):
        changed.append('.profile/stats.json')
    for name, text in [('README.template.md',template),('README.md',readme)]:
        if atomic_write(root/name, text):
            changed.append(name)
    return changed, errors
