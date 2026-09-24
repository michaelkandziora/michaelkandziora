"""Compose the original ASCII art and editable profile lines side by side."""
from __future__ import annotations

import copy
import unicodedata
from datetime import date, datetime, timezone
from itertools import zip_longest
from pathlib import Path
from typing import Any
from .model import TOKEN, atomic_write, load_cache, load_config, safe_path, validate_config

FOOTER = ('[Stats definitions](docs/METRICS.md) · Public output · '
          '`n/a`: unavailable or disabled · private repository data excluded · `*`: last successful value; see `.profile/stats.json`.\n')


def display_width(text: str) -> int:
    return sum(0 if unicodedata.combining(c) else
               2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in text)


def normalize_art(text: str) -> list[str]:
    """Crop only common outer whitespace, not whitespace inside the portrait."""
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        raise ValueError('The portrait is empty.')
    if any('\t' in line or '```' in line or
           any(unicodedata.category(c).startswith('C') for c in line) for line in lines):
        raise ValueError('The portrait must contain printable text and spaces, not tabs or code fences.')
    margin = min(len(line) - len(line.lstrip(' ')) for line in lines if line.strip())
    return [line[margin:].rstrip() for line in lines]


_ART_DENSITY = {' ': 0.0, '.': 0.20, '-': 0.38, '+': 0.68, '#': 1.0}
_ART_PALETTE = ((0.10, ' '), (0.28, '.'), (0.48, '-'), (0.73, '+'), (float('inf'), '#'))


def _art_density(character: str) -> float:
    return _ART_DENSITY.get(character, 0.55 if character.strip() else 0.0)


def resize_art(lines: list[str], target_width: int, target_height: int) -> list[str]:
    """Area-resample ASCII art while preserving sparse edges and tonal density."""
    source_height = len(lines)
    source_width = max(map(len, lines))
    canvas = [line.ljust(source_width) for line in lines]
    result: list[str] = []

    for out_y in range(target_height):
        y0 = out_y * source_height / target_height
        y1 = (out_y + 1) * source_height / target_height
        row: list[str] = []
        for out_x in range(target_width):
            x0 = out_x * source_width / target_width
            x1 = (out_x + 1) * source_width / target_width
            weighted = area = peak = 0.0

            for source_y in range(int(y0), min(source_height, int(y1) + 1)):
                overlap_y = min(y1, source_y + 1) - max(y0, source_y)
                if overlap_y <= 0:
                    continue
                for source_x in range(int(x0), min(source_width, int(x1) + 1)):
                    overlap_x = min(x1, source_x + 1) - max(x0, source_x)
                    if overlap_x <= 0:
                        continue
                    cell_area = overlap_x * overlap_y
                    density = _art_density(canvas[source_y][source_x])
                    weighted += density * cell_area
                    area += cell_area
                    peak = max(peak, density)

            average = weighted / area if area else 0.0
            density = average * 0.72 + peak * 0.28
            row.append(next(character for threshold, character in _ART_PALETTE
                            if density < threshold))
        result.append(''.join(row).rstrip())

    return result


def render_template(config: dict[str, Any], art_text: str) -> str:
    validate_config(config)
    art = normalize_art(art_text)
    layout = config['layout']
    if 'art_width' in layout:
        art = resize_art(art, layout['art_width'], layout['art_height'])
    width = max(map(display_width, art))
    label_width = max(layout['label_width'],
                      max((display_width(row['key']) for s in config['sections'] for row in s['rows']), default=0))
    rule = '─' * max(layout['rule_width'], label_width + 5)
    right = [''] * layout['top_padding'] + [config['title'], rule, '']
    for index, section in enumerate(config['sections']):
        if index:
            right.append('')
        if section['title']:
            right.extend([section['title'], rule, ''])
        for row in section['rows']:
            dots = '.' * max(2, label_width - display_width(row['key']))
            right.append(f"{row['key']} {dots} {row['value']}")
    lines = []
    for left, panel in zip_longest(art, right, fillvalue=''):
        if panel:
            lines.append(left + ' ' * (width - display_width(left) + layout['gap']) + panel)
        else:
            lines.append(left)
    return ('<!-- Generated from profile.json and assets/portrait.txt. Use python3 profile.py edit. -->\n\n'
            '```text\n' + '\n'.join(lines) + '\n```\n\n' + FOOTER)


def effective_cache(config: dict[str, Any], cache: dict[str, Any]) -> dict[str, Any]:
    if cache.get('username') and cache['username'].lower() != config['username'].lower():
        raise ValueError('Stats cache belongs to another username; remove .profile/stats.json before switching users.')
    result = copy.deepcopy(cache)
    metrics = result.setdefault('metrics', {})
    previous = cache.get('settings', {})
    if previous.get('stats') is not None and previous['stats'] != config['stats']:
        for key in ('repos', 'stars', 'stars_received', 'commits_365d', 'contributed_repos_365d'):
            metrics.pop(key, None)
    if not config['code']['enabled'] or (previous.get('code') is not None and previous['code'] != config['code']):
        for key in ('loc', 'added', 'removed'):
            metrics.pop(key, None)
    return result


def resolve_template(template: str, config: dict[str, Any], cache: dict[str, Any],
                     today: date | None = None) -> str:
    cache = effective_cache(config, cache)
    today = today or datetime.now(timezone.utc).date()
    def replace(match: Any) -> str:
        token = match.group(1)
        if token == 'username':
            return config['username']
        if token == 'date':
            return today.isoformat()
        if token.startswith('days_since:'):
            return str((today - date.fromisoformat(token.split(':', 1)[1])).days)
        if token.startswith('stats.'):
            metric = cache.get('metrics', {}).get(token[6:], {})
            value = metric.get('value')
            if value is None or metric.get('status') in ('disabled', 'missing'):
                return 'n/a'
            if type(value) is not int or value < 0:
                raise ValueError('Cached statistic must be a nonnegative integer or null.')
            return f'{value:,}' + ('*' if metric.get('status') == 'stale' else '')
        raise ValueError(f'Unknown token: {token}')
    return TOKEN.sub(replace, template)


def generate(root: Path, config: dict[str, Any] | None = None,
             cache: dict[str, Any] | None = None) -> tuple[str, str]:
    config = config or load_config(root)
    art = safe_path(root, config['art']).read_text(encoding='utf-8')
    template = render_template(config, art)
    return template, resolve_template(template, config, load_cache(root) if cache is None else cache)


def write_generated(root: Path) -> list[str]:
    template, readme = generate(root)
    return [name for name, text in [('README.template.md', template), ('README.md', readme)]
            if atomic_write(root / name, text)]


def check_generated(root: Path) -> bool:
    template, readme = generate(root)
    return all((root/name).exists() and (root/name).read_text(encoding='utf-8') == text
               for name, text in [('README.template.md', template), ('README.md', readme)])
