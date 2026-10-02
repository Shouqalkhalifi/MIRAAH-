import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# قاعدة بيانات معزولة للاختبارات
os.environ["DATABASE_PATH"] = str(ROOT / "data" / "runtime" / "test.db")
os.environ["RATE_LIMIT_PER_HOUR"] = "0"  # يُفعَّل في اختباره فقط
os.environ["SEED_CACHE"] = "off"

# قاعدة جديدة لكل جلسة اختبار حتى لا يبقى cache من مزوّد وهمي سابق
_db = Path(os.environ["DATABASE_PATH"])
if _db.exists():
    _db.unlink()
