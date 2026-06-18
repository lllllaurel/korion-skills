import argparse
import json
import re
from datetime import date, datetime, timedelta

from tool_common import connect_db, json_dumps


UNIT_ALIASES = {
    "枚": "个",
    "颗": "个",
    "只": "个",
}

CHINESE_NUMBERS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}


def normalize_unit(unit: str) -> str:
    return UNIT_ALIASES.get(unit.strip(), unit.strip())


def parse_chinese_number(token: str) -> float | None:
    token = token.strip()
    if token == "半":
        return 0.5
    if token in CHINESE_NUMBERS:
        return float(CHINESE_NUMBERS[token])
    if token == "十":
        return 10.0
    if len(token) == 2 and token[0] == "十" and token[1] in CHINESE_NUMBERS:
        return float(10 + CHINESE_NUMBERS[token[1]])
    if len(token) == 2 and token[1] == "十" and token[0] in CHINESE_NUMBERS:
        return float(CHINESE_NUMBERS[token[0]] * 10)
    return None


def parse_quantity(text: str) -> tuple[float, str] | None:
    if not text:
        return None
    raw = str(text).strip()

    for fragment in re.findall(r"\(([^()]*)\)", raw):
        parsed = parse_quantity(fragment)
        if parsed:
            return parsed

    if raw.startswith("半"):
        return 0.5, normalize_unit(raw[1:].strip())

    match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(.*)$", raw)
    if match:
        return float(match.group(1)), normalize_unit(match.group(2))

    match = re.match(r"^\s*([零一二两三四五六七八九十半]+)\s*(.*)$", raw)
    if match:
        parsed_num = parse_chinese_number(match.group(1))
        if parsed_num is not None:
            return parsed_num, normalize_unit(match.group(2))

    return None


def format_quantity(amount: float, unit: str) -> str:
    if abs(amount - round(amount)) < 1e-9:
        amount_text = str(int(round(amount)))
    else:
        amount_text = f"{amount:.2f}".rstrip("0").rstrip(".")
    return f"{amount_text}{unit}".strip()


def add_foods(food_arr: str) -> dict:
    payload = json.loads(food_arr)
    if not isinstance(payload, list) or not payload:
        raise ValueError("food_arr 必须是非空 JSON 数组")

    inserted = []
    conn = connect_db()
    try:
        cursor = conn.cursor()
        for item in payload:
            food_name = str(item.get("food_name", "")).strip()
            quantity = str(item.get("quantity", "")).strip()
            storage_location = str(item.get("storage_location", "未说明")).strip() or "未说明"
            expire_date = str(item.get("expire_date", "")).strip()

            if not food_name or not quantity or not expire_date:
                raise ValueError("food_name、quantity、expire_date 为必填字段")

            datetime.strptime(expire_date, "%Y-%m-%d")
            cursor.execute(
                """
                INSERT INTO tb_inventory (food_name, quantity, storage_location, expire_date)
                VALUES (?, ?, ?, ?)
                """,
                (food_name, quantity, storage_location, expire_date),
            )
            inserted.append(
                {
                    "inventory_id": cursor.lastrowid,
                    "food_name": food_name,
                    "quantity": quantity,
                    "storage_location": storage_location,
                    "expire_date": expire_date,
                }
            )
        conn.commit()
    finally:
        conn.close()

    return {"success": True, "inserted_count": len(inserted), "items": inserted}


def list_inventory(food_name: str | None, location: str | None, include_expired: bool) -> dict:
    sql = """
        SELECT inventory_id, food_name, quantity, storage_location, added_date, expire_date
        FROM tb_inventory
        WHERE 1 = 1
    """
    params: list[str] = []
    if food_name:
        sql += " AND food_name = ?"
        params.append(food_name)
    if location:
        sql += " AND storage_location = ?"
        params.append(location)
    if not include_expired:
        sql += " AND (expire_date IS NULL OR expire_date >= ?)"
        params.append(date.today().isoformat())
    sql += " ORDER BY COALESCE(expire_date, '9999-12-31') ASC, added_date ASC"

    conn = connect_db()
    try:
        rows = [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()

    return {"success": True, "count": len(rows), "items": rows}


def list_expiring(days: int) -> dict:
    today = date.today()
    deadline = today + timedelta(days=days)
    conn = connect_db()
    try:
        rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT inventory_id, food_name, quantity, storage_location, expire_date
                FROM tb_inventory
                WHERE expire_date IS NOT NULL
                  AND expire_date >= ?
                  AND expire_date <= ?
                ORDER BY expire_date ASC, added_date ASC
                """,
                (today.isoformat(), deadline.isoformat()),
            ).fetchall()
        ]
    finally:
        conn.close()

    return {
        "success": True,
        "days": days,
        "today": today.isoformat(),
        "deadline": deadline.isoformat(),
        "count": len(rows),
        "items": rows,
    }


def consume_inventory(food_name: str, quantity: str | None, remove_all: bool) -> dict:
    conn = connect_db()
    try:
        cursor = conn.cursor()
        rows = cursor.execute(
            """
            SELECT inventory_id, food_name, quantity, storage_location, expire_date, added_date
            FROM tb_inventory
            WHERE food_name = ?
            ORDER BY COALESCE(expire_date, '9999-12-31') ASC, added_date ASC
            """,
            (food_name,),
        ).fetchall()

        if not rows:
            return {"success": False, "message": f"库存中未找到食材：{food_name}"}

        if remove_all:
            deleted = cursor.execute(
                "DELETE FROM tb_inventory WHERE food_name = ?",
                (food_name,),
            ).rowcount
            conn.commit()
            return {"success": True, "removed_all": True, "deleted_count": deleted}

        if not quantity:
            return {"success": False, "message": "consume 模式下需要 quantity，或使用 --remove-all"}

        parsed_need = parse_quantity(quantity)
        if not parsed_need:
            return {"success": False, "message": f"无法解析消耗数量：{quantity}"}

        remaining_amount, need_unit = parsed_need
        updates = []
        skipped = []

        for row in rows:
            if remaining_amount <= 0:
                break

            parsed_stock = parse_quantity(row["quantity"])
            if not parsed_stock:
                skipped.append(
                    {
                        "inventory_id": row["inventory_id"],
                        "quantity": row["quantity"],
                        "reason": "无法解析库存数量",
                    }
                )
                continue

            stock_amount, stock_unit = parsed_stock
            if need_unit and stock_unit and normalize_unit(need_unit) != normalize_unit(stock_unit):
                skipped.append(
                    {
                        "inventory_id": row["inventory_id"],
                        "quantity": row["quantity"],
                        "reason": f"单位不匹配：库存 {stock_unit}，消耗 {need_unit}",
                    }
                )
                continue

            used_amount = min(stock_amount, remaining_amount)
            new_amount = stock_amount - used_amount
            remaining_amount -= used_amount

            if new_amount <= 1e-9:
                cursor.execute(
                    "DELETE FROM tb_inventory WHERE inventory_id = ?",
                    (row["inventory_id"],),
                )
                updates.append(
                    {
                        "inventory_id": row["inventory_id"],
                        "action": "deleted",
                        "used": format_quantity(used_amount, stock_unit or need_unit),
                    }
                )
            else:
                new_quantity = format_quantity(new_amount, stock_unit or need_unit)
                cursor.execute(
                    "UPDATE tb_inventory SET quantity = ? WHERE inventory_id = ?",
                    (new_quantity, row["inventory_id"]),
                )
                updates.append(
                    {
                        "inventory_id": row["inventory_id"],
                        "action": "updated",
                        "used": format_quantity(used_amount, stock_unit or need_unit),
                        "new_quantity": new_quantity,
                    }
                )

        conn.commit()

        success = remaining_amount <= 1e-9
        result = {
            "success": success,
            "food_name": food_name,
            "requested_quantity": quantity,
            "updates": updates,
            "skipped": skipped,
        }
        if not success:
            result["message"] = f"库存不足或部分数量无法安全扣减，仍剩 {format_quantity(remaining_amount, need_unit)} 未处理"
        return result
    finally:
        conn.close()


def build_suggestions(days: int) -> dict:
    expiring = list_expiring(days)
    inventory = list_inventory(food_name=None, location=None, include_expired=False)["items"]
    low_stock = []
    for item in inventory:
        parsed = parse_quantity(item["quantity"])
        if parsed and parsed[0] <= 1:
            low_stock.append(item)

    return {
        "success": True,
        "expiring_items": expiring["items"],
        "low_stock_items": low_stock,
        "suggestions": [
            "优先处理临近过期食材，建议按到期日从近到远安排这两天的餐次。",
            "对数量只剩 1 份左右的食材，可以结合常做菜谱提前补货。",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="冰箱与库存管理工具")
    subparsers = parser.add_subparsers(dest="action", required=True)

    add_parser = subparsers.add_parser("add", help="新增库存")
    add_parser.add_argument("--food-arr", required=True, help="JSON 数组字符串")

    list_parser = subparsers.add_parser("list", help="查询库存")
    list_parser.add_argument("--food-name")
    list_parser.add_argument("--location")
    list_parser.add_argument("--include-expired", action="store_true")

    expiring_parser = subparsers.add_parser("expiring", help="查询临期库存")
    expiring_parser.add_argument("--days", type=int, default=3)

    consume_parser = subparsers.add_parser("consume", help="扣减库存")
    consume_parser.add_argument("--food-name", required=True)
    consume_parser.add_argument("--quantity")
    consume_parser.add_argument("--remove-all", action="store_true")

    suggestion_parser = subparsers.add_parser("suggestions", help="补货与整理建议")
    suggestion_parser.add_argument("--days", type=int, default=3)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.action == "add":
        result = add_foods(args.food_arr)
    elif args.action == "list":
        result = list_inventory(args.food_name, args.location, args.include_expired)
    elif args.action == "expiring":
        result = list_expiring(args.days)
    elif args.action == "consume":
        result = consume_inventory(args.food_name, args.quantity, args.remove_all)
    else:
        result = build_suggestions(args.days)

    print(json_dumps(result))


if __name__ == "__main__":
    main()

