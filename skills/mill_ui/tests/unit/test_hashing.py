
import unittest
from skills.mill_ui.core.hashing import dump_canonical, stable_hash
class TestHashing(unittest.TestCase):
    def test_order(self):
        a=dump_canonical({'b':1,'a':2}); self.assertLess(a.find('\n  "a"'), a.find('\n  "b"'))
    def test_hash(self):
        self.assertNotEqual(stable_hash({'a':1}), stable_hash({'a':2}))
        self.assertEqual(stable_hash({'a':1,'b':2}), stable_hash({'b':2,'a':1}))
