
import sys, unittest
from pathlib import Path
def main()->int:
    start_dir=Path(__file__).parent/'unit'
    skills_root=(Path(__file__).resolve().parents[2])
    if str(skills_root) not in sys.path: sys.path.insert(0, str(skills_root))
    suite=unittest.defaultTestLoader.discover(str(start_dir), pattern='test_*.py', top_level_dir=str(skills_root))
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
if __name__=='__main__': raise SystemExit(main())
