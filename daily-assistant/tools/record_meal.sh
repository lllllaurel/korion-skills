#!/bin/bash

# 接收4个位置参数
OPEN_ID=$1
MEAL_TYPE=$2
MEAL_TIME=$3
DETAILS_JSON=$4

DB_PATH="assets/keeper.db"

# 检查参数是否完整
if [ -z "$OPEN_ID" ] || [ -z "$MEAL_TYPE" ] || [ -z "$MEAL_TIME" ] || [ -z "$DETAILS_JSON" ]; then
    echo '{"success": false, "message": "缺少必要参数"}'
    exit 1
fi

# 执行 SQLite 插入操作
# 使用双引号包裹 SQL，内部变量用单引号防止特殊字符破坏语法
sqlite3 "$DB_PATH" <<EOF
INSERT INTO tb_meals (open_id, meal_type, meal_time, details)
VALUES ($OPEN_ID, '$MEAL_TYPE', '$MEAL_TIME', '$DETAILS_JSON');
EOF

# 检查上一条命令的执行状态码
if [ $? -eq 0 ]; then
    echo '{"success": true, "message": "餐食记录已成功保存"}'
else
    echo '{"success": false, "message": "数据库写入失败，请检查表结构或权限"}'
fi
