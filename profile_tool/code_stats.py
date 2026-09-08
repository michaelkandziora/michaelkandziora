"""Optional bounded Git/cloc scan; no downloaded project code is executed."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any
from .model import REPOSITORY


def safe_env() -> dict[str, str]:
    env = os.environ.copy()
    # Public clones need no credentials. Disable global Git helpers/config and LFS smudging.
    for key in list(env):
        if key.startswith('GIT_') or key in ('GH_TOKEN','GITHUB_TOKEN','GIT_ASKPASS','SSH_ASKPASS'):
            env.pop(key, None)
    env.update({'GIT_TERMINAL_PROMPT':'0', 'GIT_CONFIG_NOSYSTEM':'1',
                'GIT_CONFIG_GLOBAL':os.devnull, 'GIT_LFS_SKIP_SMUDGE':'1'})
    return env


def run_git(args: list[str], cwd: Path, timeout: int) -> bytes:
    command = ['git', '-c', 'core.hooksPath=' + os.devnull,
               '-c', 'core.fsmonitor=false', '-c', 'protocol.file.allow=never',
               '-c', 'credential.helper=', *args]
    try:
        return subprocess.run(command, cwd=cwd, env=safe_env(), check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout).stdout
    except subprocess.TimeoutExpired as exc:
        raise ValueError('Code scan exceeded its per-command timeout.') from exc
    except subprocess.CalledProcessError as exc:
        raise ValueError('Git clone/history scan failed; no partial code totals were published.') from exc


def excluded(path: str, directories: list[str], files: list[str]) -> bool:
    parts = PurePosixPath(path).parts
    return bool(parts) and (any(part in directories for part in parts[:-1]) or parts[-1] in files)


def sum_numstat(data: bytes, directories: list[str], files: list[str]) -> tuple[int, int]:
    added = removed = 0
    for record in data.split(b'\x00'):
        record = record.lstrip(b'\n')
        if not record:
            continue
        fields = record.split(b'\t', 2)
        if len(fields) != 3:
            raise ValueError('Malformed git numstat output; refusing a partial sum.')
        plus, minus, raw_path = fields
        if plus == b'-' or minus == b'-':
            continue  # Binary diffs have no line count.
        path = raw_path.decode('utf-8', errors='surrogateescape')
        if excluded(path, directories, files):
            continue
        if not plus.isdigit() or not minus.isdigit():
            raise ValueError('Invalid git numstat count.')
        added += int(plus)
        removed += int(minus)
    return added, removed


def history_churn(repo: Path, directories: list[str], files: list[str], timeout: int) -> tuple[int, int]:
    data = run_git(['log','--no-ext-diff','--no-textconv','--format=','--numstat','-z',
                    '--no-renames','--no-merges','HEAD','--'], repo, timeout)
    if len(data) > 128 * 1024 * 1024:
        raise ValueError('Git history output exceeds 128 MiB; narrow the repository scope.')
    return sum_numstat(data, directories, files)


def select_repositories(repositories: list[dict[str, Any]], code: dict[str, Any],
                        username: str) -> list[dict[str, Any]]:
    allowed = {}
    for repo in repositories:
        name = repo.get('full_name', '')
        if not REPOSITORY.fullmatch(name) or name.split('/')[0].lower() != username.lower():
            continue
        if repo.get('private') is not False or repo.get('fork') is not False:
            continue
        if code['exclude_archived'] and repo.get('archived'):
            continue
        if name.lower() == f'{username}/{username}'.lower():
            continue
        allowed[name.lower()] = repo
    requested = code['repositories']
    if requested:
        if any(name.lower() not in allowed for name in requested):
            raise ValueError('A selected repository is not eligible: public, owned, non-fork, non-profile and archive policy required.')
        selected = [allowed[name] for name in sorted({n.lower() for n in requested})]
    else:
        selected = [allowed[name] for name in sorted(allowed)]
    if len(selected) > code['max_repositories']:
        raise ValueError('Code repository limit reached; set an explicit allowlist instead of publishing partial totals.')
    for repo in selected:
        size = repo.get('size')
        if type(size) is not int or size < 0 or size > code['max_repository_kib']:
            raise ValueError('A code repository exceeds the configured size limit or has unknown size.')
    return selected


def snapshot_loc(repo: Path, code: dict[str, Any]) -> int:
    command = ['cloc', '--config=' + os.devnull, '--json', '--quiet', '--vcs=git']
    if code['exclude_dirs']:
        command.append('--exclude-dir=' + ','.join(code['exclude_dirs']))
    if code['exclude_files']:
        # cloc matches file basenames with --not-match-f (without --fullpath).
        command.append('--not-match-f=^(?:' + '|'.join(re.escape(x) for x in code['exclude_files']) + ')$')
    try:
        proc = subprocess.run(command, cwd=repo, env=safe_env(), check=True,
                              capture_output=True, timeout=code['timeout_seconds'])
        result = json.loads(proc.stdout or b'{}')
        value = result.get('SUM', {}).get('code', 0)
        if type(value) is not int or value < 0:
            raise ValueError('cloc returned an invalid count.')
        return value
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise ValueError('cloc failed or timed out; no partial LOC was published.') from exc


def scan_code(repositories: list[dict[str, Any]], code: dict[str, Any],
              username: str) -> dict[str, int]:
    selected = select_repositories(repositories, code, username)
    if not shutil.which('git') or not shutil.which('cloc'):
        raise ValueError('Code scan requires git and cloc. Install them or disable code scanning.')
    totals = {'loc':0, 'added':0, 'removed':0}
    with tempfile.TemporaryDirectory(prefix='profile-code-') as directory:
        base = Path(directory)
        for index, metadata in enumerate(selected):
            if metadata['size'] == 0:
                continue  # Empty public repository.
            repo = base / str(index)
            url = 'https://github.com/' + metadata['full_name'] + '.git'
            run_git(['clone','--quiet','--single-branch','--no-tags','--',url,str(repo)],
                    base, code['timeout_seconds'])
            added, removed = history_churn(repo, code['exclude_dirs'],code['exclude_files'],code['timeout_seconds'])
            totals['loc'] += snapshot_loc(repo, code)
            totals['added'] += added
            totals['removed'] += removed
            shutil.rmtree(repo)
    return totals
