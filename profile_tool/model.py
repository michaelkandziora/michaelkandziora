"""Validated, dependency-free configuration and atomic file writes."""
from __future__ import annotations

import json
import os
import re
import tempfile
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

METRICS = {
    'repos', 'stars', 'stars_received', 'starred', 'followers', 'following', 'public_gists',
    'pull_requests', 'commits_365d', 'contributed_repos_365d',
    'loc', 'added', 'removed',
}
TOKEN = re.compile(r'\{\{([^{}]+)\}\}')
IDENTIFIER = re.compile(r'[a-z][a-z0-9_\-]*\Z')
USERNAME = re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z')
REPOSITORY = re.compile(r'[A-Za-z0-9-]+/[A-Za-z0-9_.-]+\Z')


def read_json(path: Path) -> dict[str, Any]:
    try:
        result = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f'Cannot read JSON: {path}: {exc}') from exc
    if not isinstance(result, dict):
        raise ValueError(f'JSON root must be an object: {path}')
    return result


def atomic_write(path: Path, text: str) -> bool:
    """Replace a file only if its UTF-8 content changed; never truncate in place."""
    data = text.encode('utf-8')
    if path.exists() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


def write_json(path: Path, value: dict[str, Any]) -> bool:
    return atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + '\n')


def safe_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if path == root.resolve() or root.resolve() not in path.parents:
        raise ValueError('Configured paths must stay inside the repository.')
    return path


def validate_text(value: Any, field: str, tokens: bool = True) -> None:
    if not isinstance(value, str):
        raise ValueError(f'{field} must be text.')
    if len(value) > 4000:
        raise ValueError(f'{field} exceeds 4000 characters.')
    if '```' in value or any(unicodedata.category(ch).startswith('C') for ch in value):
        raise ValueError(f'{field}: tabs, newlines, control characters and code fences are not allowed.')
    if not tokens and ('{{' in value or '}}' in value):
        raise ValueError(f'{field} cannot contain template tokens.')
    for found in TOKEN.finditer(value):
        token = found.group(1)
        if token in ('username', 'date'):
            continue
        if token.startswith('stats.') and token[6:] in METRICS:
            continue
        if token.startswith('days_since:'):
            try:
                date.fromisoformat(token.split(':', 1)[1])
            except ValueError as exc:
                raise ValueError('days_since requires an explicit ISO date: YYYY-MM-DD.') from exc
            continue
        raise ValueError(f'Unknown template token: {{{{{token}}}}}')
    remaining = TOKEN.sub('', value)
    if '{{' in remaining or '}}' in remaining:
        raise ValueError(f'{field}: malformed template token.')


def bounded_int(value: Any, field: str, low: int, high: int) -> None:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{field} must be an integer from {low} to {high}.')


def validate_config(config: dict[str, Any]) -> None:
    if config.get('schema_version') != 1:
        raise ValueError('Unsupported profile.json schema_version (expected 1).')
    if not USERNAME.fullmatch(config.get('username', '')):
        raise ValueError('Invalid GitHub username.')
    validate_text(config.get('title'), 'title')
    if not isinstance(config.get('art'), str):
        raise ValueError('art must be a relative file path.')
    layout = config.get('layout', {})
    for key, default, low, high in [('gap', 4, 1, 30), ('label_width', 18, 1, 80),
                                  ('rule_width', 48, 10, 160), ('top_padding', 1, 0, 100)]:
        bounded_int(layout.get(key, default), f'layout.{key}', low, high)
    for key in ('art_width', 'art_height'):
        if key in layout:
            bounded_int(layout[key], f'layout.{key}', 16, 160)
    if ('art_width' in layout) != ('art_height' in layout):
        raise ValueError('layout.art_width and layout.art_height must be configured together.')
    settings = config.get('stats', {})
    if settings.get('days') != 365:
        raise ValueError('stats.days must be 365; the metric names explicitly describe this period.')
    if type(settings.get('exclude_forks')) is not bool:
        raise ValueError('stats.exclude_forks must be boolean.')
    sections = config.get('sections')
    if not isinstance(sections, list) or not sections:
        raise ValueError('At least one section is required.')
    section_ids, row_ids = set(), set()
    for section in sections:
        if not isinstance(section, dict):
            raise ValueError('Each section must be an object.')
        sid = section.get('id', '')
        if not IDENTIFIER.fullmatch(sid) or sid in section_ids:
            raise ValueError(f'Invalid or duplicate section ID: {sid}')
        section_ids.add(sid)
        validate_text(section.get('title'), 'section.title', tokens=False)
        if not isinstance(section.get('rows'), list):
            raise ValueError('section.rows must be a list.')
        for row in section['rows']:
            if not isinstance(row, dict):
                raise ValueError('Each row must be an object.')
            rid = row.get('id', '')
            if not IDENTIFIER.fullmatch(rid) or rid in row_ids:
                raise ValueError(f'Invalid or duplicate row ID: {rid}')
            row_ids.add(rid)
            validate_text(row.get('key'), 'row.key', tokens=False)
            if not row['key'].strip():
                raise ValueError('A row key cannot be empty.')
            validate_text(row.get('value'), 'row.value')
    code = config.get('code', {})
    for name in ('enabled', 'exclude_archived'):
        if type(code.get(name)) is not bool:
            raise ValueError(f'code.{name} must be boolean.')
    for key, low, high in [('max_repositories', 1, 1000), ('max_repository_kib', 1, 10000000),
                           ('timeout_seconds', 1, 900)]:
        bounded_int(code.get(key), f'code.{key}', low, high)
    for name in ('repositories', 'exclude_dirs', 'exclude_files'):
        if not isinstance(code.get(name), list) or any(not isinstance(x, str) for x in code[name]):
            raise ValueError(f'code.{name} must be a list of strings.')
    for repo in code['repositories']:
        if not REPOSITORY.fullmatch(repo) or repo.split('/')[0].lower() != config['username'].lower():
            raise ValueError('Code scope must use explicit owner/repo names owned by the configured user.')
    for name in code['exclude_dirs'] + code['exclude_files']:
        if not name or ',' in name or '/' in name or '\\' in name or name.startswith('-'):
            raise ValueError('Code exclusions must be plain directory/file basenames, without comma or slash.')
        validate_text(name, 'code exclusion', tokens=False)


def load_config(root: Path) -> dict[str, Any]:
    config = read_json(root / 'profile.json')
    validate_config(config)
    safe_path(root, config['art'])
    return config


def load_cache(root: Path) -> dict[str, Any]:
    path = root / '.profile/stats.json'
    return read_json(path) if path.exists() else {'metrics': {}}
