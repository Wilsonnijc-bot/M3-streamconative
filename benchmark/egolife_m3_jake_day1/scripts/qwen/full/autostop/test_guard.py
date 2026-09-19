import importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('guard',Path(__file__).with_name('guard.py'));g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
class GuardTests(unittest.TestCase):
 def test_running_pipeline_cannot_stop(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'pipeline_status.txt').write_text('exit_status=running\n')
   self.assertIsNone(g.check(r,r)[0])
 def test_validation_failure_cannot_stop(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'results').mkdir()
   for n in ['pipeline_status.txt','launcher_status.txt']:(r/n).write_text('exit_status=0\n')
   (r/'results/validation.json').write_text(json.dumps({'status':'failed','qa_rows':40}))
   self.assertIsNone(g.check(r,r)[0])
 def test_duplicate_question_set_cannot_stop(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'results').mkdir()
   for n in ['pipeline_status.txt','launcher_status.txt']:(r/n).write_text('exit_status=0\n')
   (r/'results/validation.json').write_text(json.dumps({'status':'complete','qa_rows':40,'problems':[]}))
   (r/'results'/g.NAMES[0]).write_text('\n'.join(json.dumps({'question_index':1,'prediction':'A'}) for _ in range(10)))
   self.assertIsNone(g.check(r,r)[0])
if __name__=='__main__':unittest.main()
