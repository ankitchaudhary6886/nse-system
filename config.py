from pathlib import Path

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
DB_PATH = DATA_DIR / "app.db"

HISTORY_YEARS = 5
SLEEP_SECONDS = 0.6

DATA_DIR.mkdir(exist_ok=True)