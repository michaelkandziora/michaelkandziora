import copy
import hashlib
import json
import unittest
from pathlib import Path

from profile_tool import render, model

ROOT = Path(__file__).resolve().parents[1]

class RenderTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'tests/fixtures/profile.json').read_text())
        self.art = (ROOT / 'tests/fixtures/assets/portrait.txt').read_text()

    def test_original_asset_unchanged(self):
        self.assertEqual(hashlib.sha256(self.art.encode()).hexdigest(),
                         '446848e0a554464e6f420a013299997d0c56fa74023872ab51da5731b16734c3')

    def test_normalization_keeps_every_non_outer_character(self):
        self.assertEqual(render.normalize_art('   A B  \n   # @ \n'), ['A B', '# @'])

    def test_alignment_preserves_portrait(self):
        text = render.render_template(self.config, self.art)
        rows = text.split('```text\n', 1)[1].split('\n```', 1)[0].splitlines()
        art = render.normalize_art(self.art)
        width = max(map(render.display_width, art))
        for index, line in enumerate(art):
            self.assertEqual(rows[index][:width].rstrip(), line)
        right = [s[width + 4:] for s in rows if len(s) > width + 4]
        self.assertIn('{{username}}@github', right)
        self.assertTrue(any(s.startswith('Repos ') for s in right))
        self.assertNotIn('\t', text)
        self.assertNotIn('<!--', text.split('```text\n')[1].split('\n```')[0])

    def test_added_rows_longer_than_portrait(self):
        self.config['sections'][0]['rows'].extend(
            {'id':f'x{i}', 'key':f'Key {i}', 'value':f'Value {i}'} for i in range(130))
        text=render.render_template(self.config,self.art)
        self.assertIn('Value 129',text)
        self.assertIn(render.normalize_art(self.art)[-1],text)

    def test_unknown_token_fails(self):
        self.config['sections'][0]['rows'][0]['value']='{{stats.repos_typo}}'
        with self.assertRaises(ValueError): model.validate_config(self.config)

    def test_duplicate_row_ids_fail(self):
        self.config['sections'][0]['rows'].append(copy.deepcopy(self.config['sections'][0]['rows'][0]))
        with self.assertRaises(ValueError): model.validate_config(self.config)

    def test_control_characters_and_fences_fail(self):
        for bad in ['a\tb','a\nb','```','\x1b[0m','a\u202eb']:
            c=copy.deepcopy(self.config);c['sections'][0]['rows'][0]['value']=bad
            with self.subTest(bad=bad), self.assertRaises(ValueError): model.validate_config(c)

    def test_repeated_render_retains_template_tokens(self):
        template=render.render_template(self.config,self.art)
        a={'metrics':{'repos':{'value':2,'status':'ok'}}}
        b={'metrics':{'repos':{'value':12345,'status':'ok'}}}
        self.assertIn('12,345',render.resolve_template(template,self.config,b))
        self.assertIn('{{stats.repos}}',template)
        self.assertIn('2  {Commit',render.resolve_template(template,self.config,a))

    def test_zero_missing_and_stale_are_distinct(self):
        template='{{stats.repos}}|{{stats.stars}}|{{stats.followers}}'
        c={'metrics':{'repos':{'value':0,'status':'ok'},'stars':{'value':7,'status':'stale'}}}
        self.assertEqual(render.resolve_template(template,self.config,c),'0|7*|n/a')

    def test_unicode_display_width(self):
        self.assertEqual(render.display_width('Ä中e\u0301'),4)

    def test_days_since_explicit_date_only(self):
        from datetime import date
        self.assertEqual(render.resolve_template('{{days_since:2020-01-01}} days',
            self.config,{},today=date(2020,1,11)),'10 days')

    def test_foreign_cache_cannot_leak(self):
        c={'username':'someone_else','metrics':{'repos':{'value':1234,'status':'ok'}}}
        with self.assertRaises(ValueError):render.resolve_template('{{stats.repos}}', self.config,c)
