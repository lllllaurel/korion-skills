import argparse
import json
import sqlite3


def add_health_metric(open_id, metric_type, value, record_time, db_path="assets/keeper.db"):
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tb_health_metrics (open_id, metric_type, value, record_time)
            VALUES (?, ?, ?, ?)
            """,
            (open_id, metric_type, value, record_time),
        )
        conn.commit()
        return {
            "success": True,
            "message": "健康指标记录已成功保存",
            "metric_id": cursor.lastrowid,
        }
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        return {"success": False, "message": f"数据库写入失败: {str(e)}"}
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--open_id", type=int, required=True, help="用户 open_id")
    parser.add_argument("--metric_type", type=str, required=True, help="指标类型")
    parser.add_argument("--value", type=str, required=True, help="指标值")
    parser.add_argument(
        "--record_time",
        type=str,
        required=True,
        help="记录时间，格式 YYYY-MM-DD HH:MM:SS",
    )
    args = parser.parse_args()

    result = add_health_metric(
        args.open_id, args.metric_type, args.value, args.record_time
    )
    print(json.dumps(result, ensure_ascii=False))
