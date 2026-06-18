import sqlite3
import json
import argparse


def add_inventory_to_db(json_array_str, db_path="assets/keeper.db"):
    """
    接收 JSON 字符串或列表格式的食材数组，解析后批量写入 tb_inventory 表
    """
    conn = None
    try:
        # 1. 兼容并解析 JSON 数据
        if isinstance(json_array_str, str):
            data_list = json.loads(json_array_str)
        elif isinstance(json_array_str, list):
            data_list = json_array_str
        else:
            return {
                "success": False,
                "message": "输入的数据类型必须是 JSON 字符串或 Python 列表",
            }

        if not data_list:
            return {"success": False, "message": "JSON 数组为空，无有效数据可存储"}

        # 2. 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 3. 提取并校验数据 (expire_date 现为必填项)
        insert_data = []
        missing_expire_count = 0

        for item in data_list:
            expire_date = item.get("expire_date")

            # 严格校验必填字段
            if expire_date is None or str(expire_date).strip() == "":
                missing_expire_count += 1
                continue  # 跳过缺少过期日期的无效记录

            food_name = item.get("food_name")
            quantity = item.get("quantity", 0)
            storage_location = item.get("storage_location")

            insert_data.append((food_name, quantity, storage_location, expire_date))

        if not insert_data:
            return {
                "success": False,
                "message": f"没有包含有效 expire_date 的数据可供插入 (共 {missing_expire_count} 条被过滤)",
            }

        # 4. 执行批量插入操作
        sql = """
            INSERT INTO tb_inventory (food_name, quantity, storage_location, expire_date) 
            VALUES (?, ?, ?, ?)
        """
        cursor.executemany(sql, insert_data)

        # 提交事务
        conn.commit()

        msg = f"成功保存 {cursor.rowcount} 条库存记录"
        if missing_expire_count > 0:
            msg += f"，另有 {missing_expire_count} 条因缺少 expire_date 被丢弃"

        return {"success": True, "message": msg}

    except json.JSONDecodeError as e:
        return {"success": False, "message": f"JSON 解析失败: {str(e)}"}
    except sqlite3.Error as e:
        if conn:
            conn.rollback()  # 发生错误时回滚事务，保证数据安全
        return {"success": False, "message": f"数据库写入失败: {str(e)}"}
    finally:
        if conn:
            conn.close()  # 确保关闭数据库连接释放资源


# --- 测试运行示例 ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--food_arr", type=str, required=True, help="JSON 格式的食材数据"
    )
    args = parser.parse_args()
    food_arr = args.food_arr
    # test_json = '''[
    #     {"food_name": "鸡蛋", "quantity": 10.5, "storage_location": "冷藏", "expire_date": "2026-07-01"},
    #     {"food_name": "牛排", "quantity": 2.0, "storage_location": "冷冻", "expire_date": "2026-12-31"},
    #     {"food_name": "牛奶", "quantity": 3.0, "storage_location": "冷藏"}
    # ]'''

    result = add_inventory_to_db(food_arr)
    print(result)

    # python tools/record_fridge.py --food_arr '[{"food_name": "鸡蛋", "quantity": "10个", "storage_location": "冷藏", "expire_date": "2026-07-01"}, {"food_name": "牛排", "quantity": "2块", "storage_location": "冷冻", "expire_date": "2026-12-31"}]'
