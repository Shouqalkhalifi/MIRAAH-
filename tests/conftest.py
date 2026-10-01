import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# قاعدة بيانات معزولة للاختبارات
os.environ["DATABASE_PATH"] = str(ROOT / "data" / "runtime" / "test.db")
