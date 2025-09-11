
import unittest
from skills.mill_ui.core.numeric import round_mm, round_feed, clamp
class TestNumeric(unittest.TestCase):
    def test_round_mm(self): self.assertEqual(round_mm(0.00051), 0.001)
    def test_round_feed(self): self.assertEqual(round_feed(123.45), 123.5)
    def test_clamp(self): self.assertEqual(clamp(11,0,10),10)
