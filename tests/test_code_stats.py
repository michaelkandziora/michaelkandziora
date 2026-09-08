import subprocess
import tempfile
import unittest
from pathlib import Path
from profile_tool import code_stats

class CodeStatsTests(unittest.TestCase):
    def test_numstat_binary_and_excluded(self):
        raw=b'3\t1\tsrc/a.py\x00-\t-\timg.png\x009\t0\tnode_modules/a.js\x00'
        self.assertEqual(code_stats.sum_numstat(raw,['node_modules'],[]),(3,1))
    def test_numstat_filename_with_tabs(self):
        self.assertEqual(code_stats.sum_numstat(b'2\t0\ta\tb.py\x00',[],[]),(2,0))
    def test_real_git_history_add_remove(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            def git(*args):
                return subprocess.run(['git','-C',td,*args],check=True,capture_output=True).stdout
            git('init','-b','main');git('config','user.name','Test');git('config','user.email','test@example.invalid')
            (p/'a.py').write_text('a=1\nb=2\n');git('add','.');git('commit','-m','one')
            (p/'a.py').write_text('a=1\n');git('add','.');git('commit','-m','two')
            self.assertEqual(code_stats.history_churn(p,[],[],10),(2,1))
    def test_scope_never_scans_private_or_forks(self):
        rows=[{'full_name':'alice/demo','private':False,'fork':False,'archived':False,'size':1},
              {'full_name':'alice/private','private':True,'fork':False,'archived':False,'size':1}]
        cfg={'repositories':[],'exclude_archived':True,'max_repositories':40,'max_repository_kib':200000}
        self.assertEqual([r['full_name'] for r in code_stats.select_repositories(rows,cfg,'alice')],['alice/demo'])
    def test_explicit_private_or_unknown_scope_fails(self):
        cfg={'repositories':['alice/missing'],'exclude_archived':True,'max_repositories':40,'max_repository_kib':200000}
        with self.assertRaises(ValueError):code_stats.select_repositories([],cfg,'alice')

class CodeBoundaryTests(unittest.TestCase):
    def test_cloc_does_not_read_user_options(self):
        import os
        from unittest.mock import patch
        cfg={'exclude_dirs':[],'exclude_files':[],'timeout_seconds':30}
        result=subprocess.CompletedProcess([],0,stdout=b'{"SUM":{"code":2}}',stderr=b'')
        with patch('profile_tool.code_stats.subprocess.run',return_value=result) as run:
            self.assertEqual(code_stats.snapshot_loc(Path('.'),cfg),2)
            self.assertIn('--config='+os.devnull,run.call_args.args[0])
    def test_git_subprocess_does_not_inherit_git_directory_or_token(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ,{'GIT_DIR':'/tmp/wrong-repo','GH_TOKEN':'sentinel'}):
            env=code_stats.safe_env()
            self.assertFalse('GIT_DIR' in env, 'GIT_DIR must not be inherited')
            self.assertFalse('GH_TOKEN' in env, 'Tokens must not be inherited')
    def test_invalid_cloc_count_is_not_zero(self):
        from unittest.mock import patch
        cfg={'exclude_dirs':[],'exclude_files':[],'timeout_seconds':30}
        result=subprocess.CompletedProcess([],0,stdout=b'{"SUM":{"code":"bad"}}',stderr=b'')
        with patch('profile_tool.code_stats.subprocess.run',return_value=result):
            with self.assertRaises(ValueError):code_stats.snapshot_loc(Path('.'),cfg)
