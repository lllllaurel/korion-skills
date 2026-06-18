import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta

from tool_common import (
    connect_db,
    json_dumps,
    load_daily_standard,
    resolve_open_id,
)


NUTRIENT_FIELDS = {
    "energyKCal": "能量(kcal)",
    "protein": "蛋白质(g)",
    "fat": "脂肪(g)",
    "CHO": "碳水(g)",
    "dietaryFiber": "膳食纤维(g)",
    "Ca": "钙(mg)",
    "K": "钾(mg)",
    "Na": "钠(mg)",
    "Mg": "镁(mg)",
    "Fe": "铁(mg)",
    "Zn": "锌(mg)",
    "vitaminC": "维生素C(mg)",
}

ALIAS_MAP = {
    "白米饭": "米饭",
    "米饭": "米饭",
    "荷包蛋": "鸡蛋",
    "鸡蛋": "鸡蛋",
    "蛋": "鸡蛋",
    "牛奶": "牛奶",
    "纯牛奶": "牛奶",
    "豆浆": "豆浆",
    "番茄": "西红柿",
    "西红柿": "西红柿",
    "香蕉": "香蕉",
    "苹果": "苹果",
    "玉米": "玉米",
    "鸡胸肉": "鸡胸肉",
    "鸡胸": "鸡胸肉",
    "牛肉": "牛肉",
    "鸡肉": "鸡肉",
    "西兰花": "西兰花",
    "生菜": "生菜",
    "黄瓜": "黄瓜",
    "面包": "面包",
    "粥": "粥",
    "面": "面条",
}


def normalize_meal_type(meal_type: str | None, meal_time: str) -> str:
    if meal_type:
        mapping = {
            "早餐": "早餐",
            "早饭": "早餐",
            "午餐": "午餐",
            "午饭": "午餐",
            "晚餐": "晚餐",
            "晚饭": "晚餐",
            "加餐": "加餐",
            "夜宵": "加餐",
            "早餐": "早餐",
            "Lunch": "午餐",
            "Dinner": "晚餐",
            "Breakfast": "早餐",
            "Snack": "加餐",
        }
        return mapping.get(meal_type, meal_type)

    hour = datetime.strptime(meal_time, "%Y-%m-%d %H:%M:%S").hour
    if hour < 10:
        return "早餐"
    if hour < 15:
        return "午餐"
    if hour < 21:
        return "晚餐"
    return "加餐"


def normalize_meal_time(meal_time: str | None) -> str:
    if not meal_time:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(meal_time, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    raise ValueError("meal_time 格式必须为 YYYY-MM-DD HH:MM[:SS]")


def record_meal(open_id: str, meal_type: str | None, meal_time: str | None, details_json: str) -> dict:
    normalized_time = normalize_meal_time(meal_time)
    normalized_type = normalize_meal_type(meal_type, normalized_time)
    details = json.loads(details_json)
    if not isinstance(details, list) or not details:
        raise ValueError("details_json 必须是非空 JSON 数组")

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tb_meals (open_id, meal_type, meal_time, details)
            VALUES (?, ?, ?, ?)
            """,
            (open_id, normalized_type, normalized_time, json.dumps(details, ensure_ascii=False)),
        )
        conn.commit()
        return {
            "success": True,
            "meal_id": cursor.lastrowid,
            "open_id": open_id,
            "meal_type": normalized_type,
            "meal_time": normalized_time,
            "details": details,
        }
    finally:
        conn.close()


def query_meals(open_id: str, days: int, limit: int) -> dict:
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    conn = connect_db()
    try:
        rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT meal_id, open_id, meal_type, meal_time, details, created_at
                FROM tb_meals
                WHERE CAST(open_id AS TEXT) = ?
                  AND meal_time >= ?
                ORDER BY meal_time DESC
                LIMIT ?
                """,
                (str(open_id), since, limit),
            ).fetchall()
        ]
    finally:
        conn.close()

    for row in rows:
        try:
            row["details"] = json.loads(row["details"]) if row["details"] else []
        except json.JSONDecodeError:
            row["details"] = []
            row["details_parse_error"] = True
    return {"success": True, "count": len(rows), "items": rows}


def infer_category(food: str) -> str:
    if any(keyword in food for keyword in ["米饭", "面", "粥", "包子", "面包", "燕麦", "红薯"]):
        return "主食"
    if any(keyword in food for keyword in ["苹果", "香蕉", "橙", "猕猴桃", "水果"]):
        return "水果"
    if any(keyword in food for keyword in ["鸡蛋", "牛奶", "豆浆", "鸡胸", "牛肉", "鸡肉", "鱼", "虾", "豆腐"]):
        return "蛋白质"
    if any(keyword in food for keyword in ["西红柿", "西兰花", "生菜", "黄瓜", "菠菜", "青椒", "玉米", "胡萝卜"]):
        return "蔬菜"
    return "其他"


def parse_multiplier(amount: str) -> tuple[float, str]:
    amount = amount.strip()
    if amount.startswith("半"):
        return 0.5, amount[1:].strip()
    match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(.*)$", amount)
    if match:
        return float(match.group(1)), match.group(2).strip()
    return 1.0, amount


def estimate_grams(food: str, amount: str) -> float:
    if not amount:
        amount = "适量"

    amount = amount.strip()
    direct_match = re.search(r"(\d+(?:\.\d+)?)\s*(g|克)", amount, re.IGNORECASE)
    if direct_match:
        return float(direct_match.group(1))

    multiplier, unit = parse_multiplier(amount)
    category = infer_category(food)
    base = None

    if "碗" in unit:
        if "米饭" in food:
            base = 150
        elif "粥" in food:
            base = 250
        else:
            base = 250
    elif "杯" in unit:
        base = 250
    elif "个" in unit:
        if "鸡蛋" in food:
            base = 50
        elif "苹果" in food:
            base = 180
        elif "香蕉" in food:
            base = 120
        elif "包子" in food:
            base = 100
        else:
            base = 100
    elif "片" in unit and "面包" in food:
        base = 30
    elif "份" in unit:
        if "沙拉" in food:
            base = 150
        elif category == "蛋白质":
            base = 120
        else:
            base = 200
    elif any(token in unit for token in ["根", "颗", "袋", "盒"]):
        if "玉米" in food:
            base = 200
        elif category == "水果":
            base = 150
        else:
            base = 100
    elif amount in {"适量", "少许", "一些"}:
        if category == "主食":
            base = 100
        elif category == "蛋白质":
            base = 80
        else:
            base = 100

    if base is None:
        if category == "主食":
            base = 100
        elif category == "蛋白质":
            base = 80
        else:
            base = 100

    return base * multiplier


def _safe_float(value: str | None) -> float:
    if value is None:
        return 0.0
    text = str(value).strip()
    if not text or text == "—" or text.upper() == "TR":
        return 0.0
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else 0.0


def _pick_best_food_row(rows: list[dict]) -> dict | None:
    if not rows:
        return None
    rows = sorted(
        rows,
        key=lambda row: (
            0 if "代表值" in row["foodName"] else 1,
            1 if "亨氏" in row["foodName"] else 0,
            len(row["foodName"]),
        ),
    )
    return rows[0]


def _query_food_rows(food_name: str) -> list[dict]:
    conn = connect_db()
    try:
        exact = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM tb_food_nutrition WHERE foodName = ?",
                (food_name,),
            ).fetchall()
        ]
        if exact:
            return exact

        like_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT * FROM tb_food_nutrition
                WHERE foodName LIKE ?
                ORDER BY LENGTH(foodName) ASC
                LIMIT 10
                """,
                (f"%{food_name}%",),
            ).fetchall()
        ]
        return like_rows
    finally:
        conn.close()


def match_food_rows(food: str) -> tuple[list[dict], list[str]]:
    normalized = re.sub(r"[（）()·\s]", "", food)
    candidates = []
    unmatched = []

    primary = ALIAS_MAP.get(food, food)
    primary_rows = _query_food_rows(primary)
    best_primary = _pick_best_food_row(primary_rows)
    if best_primary:
        return [best_primary], unmatched

    matched_aliases = []
    for alias, canonical in ALIAS_MAP.items():
        if alias in normalized and canonical not in matched_aliases:
            matched_aliases.append(canonical)

    for canonical in matched_aliases:
        rows = _query_food_rows(canonical)
        best_row = _pick_best_food_row(rows)
        if best_row:
            candidates.append(best_row)

    if candidates:
        unique = []
        seen = set()
        for row in candidates:
            if row["foodName"] not in seen:
                unique.append(row)
                seen.add(row["foodName"])
        return unique, unmatched

    fallback = _pick_best_food_row(_query_food_rows(normalized))
    if fallback:
        return [fallback], unmatched

    unmatched.append(food)
    return [], unmatched


def load_standard_targets(open_id: str) -> tuple[dict[str, float], list[str]]:
    targets: dict[str, float] = {}
    notes = []

    daily_standard = load_daily_standard(open_id)
    if daily_standard:
        carbs = daily_standard.get("宏量碳水化合物", {})
        minerals = daily_standard.get("矿物质(mg/μg统一换算标注，主单位mg)", {})
        vitamins = daily_standard.get("维生素(μg统一转mg标注)", {})
        targets["CHO"] = float(carbs.get("总碳水化合物_EAR_g_d", 0) or 0)
        fiber_value = carbs.get("膳食纤维_AI_g_d", "0")
        if isinstance(fiber_value, str) and "~" in fiber_value:
            low, high = fiber_value.split("~", 1)
            targets["dietaryFiber"] = (float(low) + float(high)) / 2
        else:
            targets["dietaryFiber"] = float(fiber_value or 0)
        targets["Ca"] = float(minerals.get("钙_RNI_mg_d", 0) or 0)
        targets["K"] = float(minerals.get("钾_AI_mg_d", 0) or 0)
        targets["Na"] = float(minerals.get("钠_AI_mg_d", 0) or 0)
        targets["Mg"] = float(minerals.get("镁_RNI_mg_d", 0) or 0)
        targets["Fe"] = float(minerals.get("铁_RNI_mg_d", 0) or 0)
        targets["Zn"] = float(minerals.get("锌_RNI_mg_d", 0) or 0)
        targets["vitaminC"] = float(vitamins.get("维生素C_RNI_mg_d", 0) or 0)
        notes.append("已使用 references/daily_standard.json 作为个性化标准。")
    else:
        notes.append("daily_standard.json 中未找到该用户标准。")

    return targets, notes


def analyze_nutrition(open_id: str, days: int) -> dict:
    meals = query_meals(open_id, days, 500)["items"]
    if not meals:
        return {
            "success": False,
            "message": f"最近 {days} 天没有可用餐食记录",
            "advice": [
                "先连续记录 3 到 5 天三餐，报告会更可靠。",
                "记录时尽量带上份量，比如 1 碗、150g、2 个。",
            ],
        }

    daily_totals: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    unmatched_foods = set()
    meal_breakdown = []

    for meal in sorted(meals, key=lambda item: item["meal_time"]):
        meal_date = meal["meal_time"][:10]
        items = meal.get("details", [])
        parsed_items = []
        for item in items:
            food = str(item.get("food", "")).strip()
            amount = str(item.get("amount", "适量")).strip() or "适量"
            grams = estimate_grams(food, amount)
            food_rows, unmatched = match_food_rows(food)
            unmatched_foods.update(unmatched)

            nutrients = defaultdict(float)
            if food_rows:
                share = grams / max(len(food_rows), 1)
                for row in food_rows:
                    for field in NUTRIENT_FIELDS:
                        nutrients[field] += _safe_float(row.get(field)) * share / 100
            else:
                unmatched_foods.add(food)

            for field, value in nutrients.items():
                daily_totals[meal_date][field] += value

            parsed_items.append(
                {
                    "food": food,
                    "amount": amount,
                    "estimated_grams": round(grams, 1),
                    "matched_foods": [row["foodName"] for row in food_rows],
                }
            )
        meal_breakdown.append(
            {
                "meal_id": meal["meal_id"],
                "meal_type": meal["meal_type"],
                "meal_time": meal["meal_time"],
                "items": parsed_items,
            }
        )

    overall_totals = defaultdict(float)
    for date_key, totals in daily_totals.items():
        for field, value in totals.items():
            overall_totals[field] += value

    day_count = len(daily_totals)
    averages = {
        field: round(overall_totals.get(field, 0.0) / day_count, 2)
        for field in NUTRIENT_FIELDS
    }
    overall = {field: round(overall_totals.get(field, 0.0), 2) for field in NUTRIENT_FIELDS}
    daily_summary = {
        day: {field: round(values.get(field, 0.0), 2) for field in NUTRIENT_FIELDS}
        for day, values in sorted(daily_totals.items())
    }

    targets, target_notes = load_standard_targets(open_id)
    comparisons = {}
    for field, target in targets.items():
        if target:
            actual = averages.get(field, 0.0)
            comparisons[field] = {
                "label": NUTRIENT_FIELDS.get(field, field),
                "daily_average": round(actual, 2),
                "target": round(target, 2),
                "ratio": round(actual / target, 2),
            }

    return {
        "success": True,
        "open_id": open_id,
        "days": days,
        "meal_count": len(meals),
        "day_count": day_count,
        "daily_summary": daily_summary,
        "overall_total": overall,
        "daily_average": averages,
        "target_comparison": comparisons,
        "meal_breakdown": meal_breakdown,
        "unmatched_foods": sorted(unmatched_foods),
        "notes": target_notes,
    }


def build_suggestions(report: dict) -> dict:
    if not report.get("success"):
        return report

    comparisons = report.get("target_comparison", {})
    suggestions = []

    def ratio_of(field: str) -> float | None:
        info = comparisons.get(field)
        return info["ratio"] if info else None

    protein_ratio = ratio_of("protein")
    fiber_ratio = ratio_of("dietaryFiber")
    vitamin_c_ratio = ratio_of("vitaminC")
    sodium_ratio = ratio_of("Na")
    carb_ratio = ratio_of("CHO")

    if protein_ratio is not None and protein_ratio < 0.8:
        suggestions.append("下一餐可以补一个明确的优质蛋白来源，比如鸡蛋、豆腐、鱼或鸡胸肉。")
    if fiber_ratio is not None and fiber_ratio < 0.8:
        suggestions.append("蔬菜和全谷物偏少，明天至少补 2 餐深色蔬菜，并把一餐主食换成粗粮。")
    if vitamin_c_ratio is not None and vitamin_c_ratio < 0.8:
        suggestions.append("水果和新鲜蔬菜摄入偏少，优先补橙子、猕猴桃、西红柿或西兰花。")
    if sodium_ratio is not None and sodium_ratio > 1.1:
        suggestions.append("钠摄入偏高，下一餐尽量避开高汤、酱料和加工食品，口味放淡一点。")
    if carb_ratio is not None and carb_ratio > 1.2:
        suggestions.append("主食摄入偏多，下一餐主食可以减半，并增加蔬菜和蛋白质比例。")

    if not suggestions:
        suggestions.extend(
            [
                "整体结构还算平衡，继续保持三餐都有主食、蛋白质和蔬菜的组合。",
                "如果想让记录更准，后续尽量补上克数或更明确的份量。",
            ]
        )

    report["suggestions"] = suggestions[:4]
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="饮食与营养管理工具")
    subparsers = parser.add_subparsers(dest="action", required=True)

    record_parser = subparsers.add_parser("record", help="记录餐食")
    record_parser.add_argument("--open-id")
    record_parser.add_argument("--member-name")
    record_parser.add_argument("--meal-type")
    record_parser.add_argument("--meal-time")
    record_parser.add_argument("--details-json", required=True)

    meals_parser = subparsers.add_parser("meals", help="查询近几天餐食")
    meals_parser.add_argument("--open-id")
    meals_parser.add_argument("--member-name")
    meals_parser.add_argument("--days", type=int, default=5)
    meals_parser.add_argument("--limit", type=int, default=50)

    report_parser = subparsers.add_parser("report", help="生成营养报告")
    report_parser.add_argument("--open-id")
    report_parser.add_argument("--member-name")
    report_parser.add_argument("--days", type=int, default=5)

    suggest_parser = subparsers.add_parser("suggest", help="给出饮食建议")
    suggest_parser.add_argument("--open-id")
    suggest_parser.add_argument("--member-name")
    suggest_parser.add_argument("--days", type=int, default=5)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    open_id = resolve_open_id(args.open_id, getattr(args, "member_name", None))

    if args.action == "record":
        result = record_meal(open_id, args.meal_type, args.meal_time, args.details_json)
    elif args.action == "meals":
        result = query_meals(open_id, args.days, args.limit)
    elif args.action == "report":
        result = analyze_nutrition(open_id, args.days)
    else:
        result = build_suggestions(analyze_nutrition(open_id, args.days))

    print(json_dumps(result))


if __name__ == "__main__":
    main()
