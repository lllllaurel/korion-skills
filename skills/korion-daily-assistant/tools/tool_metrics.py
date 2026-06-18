import argparse
from datetime import datetime, timedelta

from tool_common import connect_db, json_dumps, resolve_open_id


def normalize_record_time(record_time: str | None) -> str:
    if not record_time:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(record_time, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    raise ValueError("record_time 格式必须为 YYYY-MM-DD HH:MM[:SS]")


def record_metric(open_id: str, metric_type: str, value: str, record_time: str | None) -> dict:
    normalized_time = normalize_record_time(record_time)
    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tb_health_metrics (open_id, metric_type, value, record_time)
            VALUES (?, ?, ?, ?)
            """,
            (open_id, metric_type, value, normalized_time),
        )
        conn.commit()
        return {
            "success": True,
            "metric_id": cursor.lastrowid,
            "open_id": open_id,
            "metric_type": metric_type,
            "value": value,
            "record_time": normalized_time,
        }
    finally:
        conn.close()


def query_metrics(open_id: str, metric_type: str | None, days: int, limit: int) -> dict:
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    sql = """
        SELECT metric_id, open_id, metric_type, value, record_time, created_at
        FROM tb_health_metrics
        WHERE CAST(open_id AS TEXT) = ?
          AND record_time >= ?
    """
    params: list[str | int] = [str(open_id), since]
    if metric_type:
        sql += " AND metric_type = ?"
        params.append(metric_type)
    sql += " ORDER BY record_time DESC LIMIT ?"
    params.append(limit)

    conn = connect_db()
    try:
        rows = [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()
    return {"success": True, "count": len(rows), "items": rows}


def _parse_single_metric(value: str) -> float | None:
    import re

    match = re.search(r"(\d+(?:\.\d+)?)", value)
    return float(match.group(1)) if match else None


def _parse_blood_pressure(value: str) -> tuple[float, float] | None:
    import re

    match = re.search(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", value)
    if not match:
        return None
    return float(match.group(1)), float(match.group(2))


def build_trend(open_id: str, metric_type: str, days: int) -> dict:
    rows = query_metrics(open_id, metric_type, days, 100)["items"]
    rows = list(reversed(rows))
    if not rows:
        return {"success": False, "message": "最近没有可用指标记录"}

    if metric_type == "血压":
        values = []
        for row in rows:
            parsed = _parse_blood_pressure(row["value"])
            if parsed:
                values.append(parsed)
        if not values:
            return {"success": False, "message": "血压记录缺少可解析数值"}

        avg_sys = sum(v[0] for v in values) / len(values)
        avg_dia = sum(v[1] for v in values) / len(values)
        latest = values[-1]
        first = values[0]
        return {
            "success": True,
            "metric_type": metric_type,
            "sample_count": len(values),
            "latest": {"systolic": latest[0], "diastolic": latest[1]},
            "average": {"systolic": round(avg_sys, 1), "diastolic": round(avg_dia, 1)},
            "change": {
                "systolic": round(latest[0] - first[0], 1),
                "diastolic": round(latest[1] - first[1], 1),
            },
        }

    values = []
    for row in rows:
        parsed = _parse_single_metric(row["value"])
        if parsed is not None:
            values.append(parsed)
    if not values:
        return {"success": False, "message": "记录缺少可解析数值"}

    latest = values[-1]
    first = values[0]
    change = latest - first
    if abs(change) < 0.3:
        trend = "基本稳定"
    elif change > 0:
        trend = "呈上升趋势"
    else:
        trend = "呈下降趋势"

    return {
        "success": True,
        "metric_type": metric_type,
        "sample_count": len(values),
        "latest": latest,
        "min": min(values),
        "max": max(values),
        "average": round(sum(values) / len(values), 2),
        "change": round(change, 2),
        "trend": trend,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="身体指标管理工具")
    subparsers = parser.add_subparsers(dest="action", required=True)

    record_parser = subparsers.add_parser("record", help="记录指标")
    record_parser.add_argument("--open-id")
    record_parser.add_argument("--member-name")
    record_parser.add_argument("--metric-type", required=True)
    record_parser.add_argument("--value", required=True)
    record_parser.add_argument("--record-time")

    query_parser = subparsers.add_parser("query", help="查询指标")
    query_parser.add_argument("--open-id")
    query_parser.add_argument("--member-name")
    query_parser.add_argument("--metric-type")
    query_parser.add_argument("--days", type=int, default=30)
    query_parser.add_argument("--limit", type=int, default=20)

    trend_parser = subparsers.add_parser("trend", help="查看趋势")
    trend_parser.add_argument("--open-id")
    trend_parser.add_argument("--member-name")
    trend_parser.add_argument("--metric-type", required=True)
    trend_parser.add_argument("--days", type=int, default=30)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    open_id = resolve_open_id(args.open_id, getattr(args, "member_name", None))

    if args.action == "record":
        result = record_metric(open_id, args.metric_type, args.value, args.record_time)
    elif args.action == "query":
        result = query_metrics(open_id, args.metric_type, args.days, args.limit)
    else:
        result = build_trend(open_id, args.metric_type, args.days)

    print(json_dumps(result))


if __name__ == "__main__":
    main()

