import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        for name in ['profile.json','assets','.profile']:
            src=ROOT/'tests/fixtures'/name;dst=self.root/name
            if src.is_dir():shutil.copytree(src,dst)
            else:shutil.copy2(src,dst)
    def run_cli(self,*args,ok=True,input=None):
        p=subprocess.run([sys.executable,str(ROOT/'profile.py'),'--root',str(self.root),*args],
                         capture_output=True,text=True,input=input)
        if ok:self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        else:self.assertNotEqual(p.returncode,0)
        return p
    def config(self):return json.loads((self.root/'profile.json').read_text())
    def test_render_then_check(self):
        self.run_cli('render');self.run_cli('check')
        p=self.root/'README.md';p.write_text(p.read_text()+'bad')
        self.run_cli('check',ok=False)
    def test_set_rename_add_remove_and_move(self):
        self.run_cli('set','ide','--value','VS Code + Neovim')
        self.run_cli('rename','ide','--key','Editors')
        self.run_cli('add','--section','languages','--id','frameworks','--key','Frameworks','--value','FastAPI, React')
        text=(self.root/'README.md').read_text()
        self.assertIn('VS Code + Neovim',text);self.assertIn('FastAPI, React',text)
        self.run_cli('move','frameworks','--section','system','--before','ide')
        ids=[x['id'] for x in self.config()['sections'][0]['rows']]
        self.assertLess(ids.index('frameworks'),ids.index('ide'))
        self.run_cli('remove','frameworks')
        self.assertNotIn('FastAPI, React',(self.root/'README.md').read_text())
    def test_invalid_edit_is_atomic(self):
        before=(self.root/'profile.json').read_bytes()
        self.run_cli('set','ide','--value','{{stats.typo}}',ok=False)
        self.assertEqual(before,(self.root/'profile.json').read_bytes())
    def test_new_section_and_dynamic_row(self):
        self.run_cli('section-add','projects','--title','Projects')
        self.run_cli('add','--section','projects','--id','follows','--key','Following','--value','{{stats.following}}')
        self.assertIn('{{stats.following}}',(self.root/'README.template.md').read_text())
    def test_code_enable_records_explicit_scope(self):
        self.run_cli('code','enable','--repo','michaelkandziora/demo')
        c=self.config()['code'];self.assertTrue(c['enabled']);self.assertEqual(c['repositories'],['michaelkandziora/demo'])
        self.run_cli('code','disable');self.assertFalse(self.config()['code']['enabled'])
    def test_interactive_editor(self):
        self.run_cli('edit',input='set\nide\nNeovim\nquit\n')
        self.assertIn('Neovim',(self.root/'README.md').read_text())
