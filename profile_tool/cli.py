"""Interactive editor and scriptable commands; mutations regenerate both Markdown files."""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any
from . import render, stats
from .github import APIError
from .model import METRICS, atomic_write, load_config, validate_config, write_json


def section_by_id(config: dict[str, Any], sid: str) -> dict[str, Any]:
    for section in config['sections']:
        if section['id'] == sid:
            return section
    raise ValueError(f'Unknown section ID: {sid}. Use `show` to list IDs.')


def find_row(config: dict[str, Any], rid: str) -> tuple[dict[str, Any], dict[str, Any]]:
    for section in config['sections']:
        for row in section['rows']:
            if row['id'] == rid:
                return section, row
    raise ValueError(f'Unknown row ID: {rid}. Use `show` to list IDs.')


def slug(value: str) -> str:
    ascii_text = unicodedata.normalize('NFKD', value).encode('ascii','ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+','_',ascii_text).strip('_')


def show(config: dict[str, Any]) -> None:
    for section in config['sections']:
        print(f"\n[{section['id']}] {section['title']}")
        for row in section['rows']:
            print(f"  {row['id']:<24} {row['key']:<22} {row['value']}")


def save(root: Path, config: dict[str, Any]) -> None:
    validate_config(config)
    # Build all output in memory first, so invalid input never corrupts the config.
    template, readme = render.generate(root, config)
    write_json(root/'profile.json', config)
    atomic_write(root/'README.template.md', template)
    atomic_write(root/'README.md', readme)


def mutate(root: Path, args: argparse.Namespace) -> None:
    config = copy.deepcopy(load_config(root))
    command = args.command
    if command == 'set':
        find_row(config,args.id)[1]['value'] = args.value
    elif command == 'rename':
        find_row(config,args.id)[1]['key'] = args.key
    elif command == 'add':
        section = section_by_id(config,args.section)
        row = {'id':args.id or slug(args.key), 'key':args.key, 'value':args.value}
        index = len(section['rows'])
        if args.before:
            target_section, target = find_row(config,args.before)
            if target_section is not section:
                raise ValueError('--before must reference a row in the destination section.')
            index = section['rows'].index(target)
        section['rows'].insert(index,row)
    elif command == 'remove':
        section,row = find_row(config,args.id)
        section['rows'].remove(row)
    elif command == 'move':
        source,row = find_row(config,args.id)
        destination = section_by_id(config,args.section)
        if args.before == args.id:
            raise ValueError('A row cannot be moved before itself.')
        source['rows'].remove(row)
        index = len(destination['rows'])
        if args.before:
            target_section, target = find_row(config,args.before)
            if target_section is not destination:
                raise ValueError('--before must be in the destination section.')
            index = destination['rows'].index(target)
        destination['rows'].insert(index,row)
    elif command == 'section-add':
        config['sections'].append({'id':args.id,'title':args.title,'rows':[]})
    elif command == 'section-rename':
        section_by_id(config,args.id)['title'] = args.title
    elif command == 'section-remove':
        section = section_by_id(config,args.id)
        if section['rows'] and not args.with_rows:
            raise ValueError('Section is not empty. Use --with-rows to explicitly remove its rows as well.')
        config['sections'].remove(section)
    elif command == 'section-move':
        section = section_by_id(config,args.id)
        if args.before == args.id:
            raise ValueError('A section cannot be moved before itself.')
        config['sections'].remove(section)
        index = len(config['sections']) if not args.before else config['sections'].index(section_by_id(config,args.before))
        config['sections'].insert(index,section)
    elif command == 'layout':
        for key in ('gap','label_width','rule_width','top_padding'):
            value = getattr(args,key,None)
            if value is not None:
                config['layout'][key] = value
    elif command == 'code':
        if args.mode == 'show':
            print(json.dumps(config['code'],ensure_ascii=False,indent=2))
            return
        config['code']['enabled'] = args.mode == 'enable'
        if args.repo:
            config['code']['repositories'] = args.repo
    else:
        raise ValueError(f'Unknown editing command: {command}')
    save(root,config)
    print('Saved profile.json; regenerated README.template.md and README.md.')


def interactive(root: Path) -> None:
    print('ASCII profile editor — every successful edit is saved and rendered immediately.')
    print('Commands: show, set, rename, add, remove, move, section, preview, quit')
    show(load_config(root))
    while True:
        try:
            command = input('\nprofile> ').strip().lower()
            if command in ('q','quit','exit'):
                return
            if command in ('','show'):
                show(load_config(root));continue
            if command == 'preview':
                print(render.generate(root)[1]);continue
            if command == 'set':
                argv=['set',input('Row ID: ').strip(),'--value',input('New value (empty clears): ')]
            elif command == 'rename':
                argv=['rename',input('Row ID: ').strip(),'--key',input('New key / label: ')]
            elif command == 'add':
                section=input('Section ID: ').strip();key=input('Key / label: ')
                rid=input(f'Row ID [{slug(key)}]: ').strip() or slug(key)
                argv=['add','--section',section,'--id',rid,'--key',key,'--value',input('Value or {{stats.token}}: ')]
            elif command == 'remove':
                argv=['remove',input('Row ID to remove: ').strip()]
            elif command == 'move':
                argv=['move',input('Row ID: ').strip(),'--section',input('Destination section ID: ').strip()]
                before=input('Before row ID (empty = end): ').strip()
                if before:argv += ['--before',before]
            elif command == 'section':
                argv=['section-add',input('New section ID: ').strip(),'--title',input('Section title: ')]
            else:
                print('Unknown command. Use show, set, rename, add, remove, move, section, preview or quit.');continue
            mutate(root, parser().parse_args(argv))
        except (EOFError, KeyboardInterrupt):
            print('\nEditor closed. Successful previous edits are already saved.');return
        except (ValueError, OSError) as exc:
            print(f'Error: {exc}',file=sys.stderr)


def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(description='Edit and generate a classic ASCII GitHub profile README.')
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1],help='Repository root (before the subcommand).')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('show',help='Show sections, stable row IDs, keys and values.')
    sub.add_parser('edit',help='Start the interactive editor; no network access.')
    sub.add_parser('render',help='Generate template + README from the last cached statistics.')
    preview=sub.add_parser('preview',help='Print a preview without writing files.')
    preview.add_argument('--template',action='store_true')
    sub.add_parser('check',help='Verify that checked-in Markdown matches the sources.')
    sub.add_parser('metrics',help='List supported dynamic metric tokens.')
    update=sub.add_parser('update',help='Fetch public stats and generate template + README.')
    update.add_argument('--strict',action='store_true',help='Abort without writes on any metric retrieval error.')
    s=sub.add_parser('set',help='Change a row value, retaining its ID and label.')
    s.add_argument('id');s.add_argument('--value',required=True)
    s=sub.add_parser('rename',help='Rename the visible row key, retaining its stable ID.')
    s.add_argument('id');s.add_argument('--key',required=True)
    s=sub.add_parser('add',help='Add a row to a section.')
    s.add_argument('--section',required=True);s.add_argument('--id');s.add_argument('--key',required=True)
    s.add_argument('--value',required=True);s.add_argument('--before')
    s=sub.add_parser('remove',help='Remove a row by ID.');s.add_argument('id')
    s=sub.add_parser('move',help='Move a row into a section and optionally before another row.')
    s.add_argument('id');s.add_argument('--section',required=True);s.add_argument('--before')
    for name in ('section-add','section-rename'):
        s=sub.add_parser(name);s.add_argument('id');s.add_argument('--title',required=True)
    s=sub.add_parser('section-remove');s.add_argument('id');s.add_argument('--with-rows',action='store_true')
    s=sub.add_parser('section-move');s.add_argument('id');s.add_argument('--before')
    s=sub.add_parser('layout',help='Change spacing, dot-leader width or heading separator width.')
    for name in ('gap','label-width','rule-width','top-padding'):
        s.add_argument('--'+name,type=int)
    s=sub.add_parser('code',help='Configure optional Git/cloc scanning of owned public repositories.')
    s.add_argument('mode',choices=['enable','disable','show'])
    s.add_argument('--repo',action='append',help='Explicit owner/repo allowlist; repeat for multiple repositories.')
    return p


def main(argv: list[str] | None = None) -> int:
    args=parser().parse_args(argv)
    root=args.root.resolve()
    try:
        if args.command == 'show':
            show(load_config(root))
        elif args.command == 'edit':
            interactive(root)
        elif args.command == 'render':
            changed=render.write_generated(root)
            print('Generated: '+', '.join(changed) if changed else 'Already up to date.')
        elif args.command == 'preview':
            generated=render.generate(root)
            print(generated[0 if args.template else 1],end='')
        elif args.command == 'check':
            if not render.check_generated(root):
                print('Generated files differ. Run: python3 profile.py render',file=sys.stderr);return 1
            print('Template and README match their sources.')
        elif args.command == 'metrics':
            for name in sorted(METRICS):print('{{stats.'+name+'}}')
            print('{{username}}\n{{date}}\n{{days_since:YYYY-MM-DD}}')
        elif args.command == 'update':
            changed,errors=stats.update(root,strict=args.strict)
            print('Updated: '+', '.join(changed) if changed else 'Already up to date.')
            for message in sorted(set(errors.values())):print('Warning: '+message,file=sys.stderr)
        else:
            mutate(root,args)
        return 0
    except (ValueError, APIError, OSError) as exc:
        print(f'Error: {exc}',file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
