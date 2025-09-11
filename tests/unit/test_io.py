
import unittest, json, os, tempfile
from skills.mill_ui.api.io import save_json, load_json, dump_canonical, stable_hash
class TestIO(unittest.TestCase):
    def test_save_load(self):
        with tempfile.TemporaryDirectory() as d:
            p=os.path.join(d,'obj.json'); saved=save_json(p, {'b':1,'a':2})
            self.assertTrue(os.path.exists(saved))
            obj=load_json(saved); self.assertEqual(obj['a'],2)
            self.assertEqual(stable_hash(obj), stable_hash({'a':2,'b':1}))
