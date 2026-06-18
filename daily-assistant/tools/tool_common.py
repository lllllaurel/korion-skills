import json
import re
import sqlite3
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "assets" / "keeper.db"
INIT_SQL_PATH = ROOT_DIR / "tools" / "init_db.sql"
MEMBER_INFO_PATH = ROOT_DIR / "references" / "member_info.json"
DAILY_STANDARD_PATH = ROOT_DIR / "references" / "daily_standard.json"
USER_NUTRITION_PATH = ROOT_DIR / "references" / "user_nutrition.json"


def json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def load_json_file(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    # 兼容 references/ 中可能出现的尾逗号。
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return json.loads(text)


def ensure_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        init_sql = INIT_SQL_PATH.read_text(encoding="utf-8")
        conn.executescript(init_sql)
        conn.commit()
    finally:
        conn.close()


def connect_db() -> sqlite3.Connection:
    ensure_database()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def resolve_open_id(open_id: str | None = None, member_name: str | None = None) -> str:
    if open_id:
        return str(open_id)
    if not member_name:
        raise ValueError("需要提供 open_id 或 member_name")

    members = load_json_file(MEMBER_INFO_PATH)
    for member in members:
        if member.get("称呼") == member_name:
            return str(member["open_id"])

    raise ValueError(f"未在 references/member_info.json 中找到成员：{member_name}")


def load_daily_standard(open_id: str) -> dict[str, Any] | None:
    data = load_json_file(DAILY_STANDARD_PATH)
    return data.get(open_id)

