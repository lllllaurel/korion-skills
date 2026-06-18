-- ==========================================
-- Keeper 数据库初始化脚本 (SQLite)
-- 适用场景：数据库文件不存在 / 缺失部分业务表
-- ==========================================

-- 1. 用户基本信息表
-- CREATE TABLE IF NOT EXISTS tb_users (
--     user_id INTEGER PRIMARY KEY AUTOINCREMENT,
--     open_id Integer NOT NULL,
--     name TEXT NOT NULL,
--     age INTEGER,
--     gender TEXT,
--     height REAL,
--     weight REAL,
--     preferences TEXT,       -- 偏好与禁忌（建议以JSON字符串格式存储）
--     other_info TEXT,        -- 其他信息
--     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
-- );

-- 2. 餐食记录表
CREATE TABLE IF NOT EXISTS tb_meals (
    meal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    open_id TEXT NOT NULL,
    meal_type TEXT NOT NULL, -- 早餐/午餐/晚餐/加餐
    meal_time TIMESTAMP NOT NULL,
    details TEXT,           -- 餐食详情（建议以JSON字符串格式存储）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. 食材基础信息表
CREATE TABLE IF NOT EXISTS tb_ingredients (
    ingredient_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT,
    unit TEXT,              -- 默认单位（如：克、个、根）
    shelf_life_days INTEGER,-- 保质期天数
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. 冰箱库存表
CREATE TABLE if not exists tb_inventory (     
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,     
    food_name TEXT NOT NULL,
    quantity Text NOT NULL,     
    storage_location TEXT, 
    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,     
    expire_date DATE
);

-- 5. 健康指标记录表
CREATE TABLE IF NOT EXISTS tb_health_metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    open_id TEXT NOT NULL,
    metric_type TEXT NOT NULL, -- 血压/血糖/体重等
    value TEXT NOT NULL,
    record_time TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. 健康日常任务表
CREATE TABLE IF NOT EXISTS tb_health_routines (
    routine_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    task_type TEXT NOT NULL,
    frequency TEXT,         -- 频率描述（如：每日一次、每周三次）
    last_completed_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES tb_users(user_id) ON DELETE CASCADE
);

-- 7. 食物gi表
CREATE TABLE IF NOT EXISTS tb_food_gi (
    id INTEGER PRIMARY KEY,             
    food_group TEXT,             
    food_name TEXT,             
    gi REAL         
);

-- 8. 食物营养信息表
CREATE TABLE IF NOT EXISTS tb_food_nutrition (             
    id INTEGER PRIMARY KEY AUTOINCREMENT,             
    foodCode TEXT UNIQUE,             
    foodName TEXT,             
    edible TEXT,             
    water TEXT,             
    energyKCal TEXT,             
    energyKJ TEXT,             
    protein TEXT,             
    fat TEXT,             
    CHO TEXT,             
    dietaryFiber TEXT,             
    cholesterol TEXT,             
    ash TEXT,             
    vitaminA TEXT,             
    carotene TEXT,             
    retinol TEXT,             
    thiamin TEXT,             
    riboflavin TEXT,             
    niacin TEXT,             
    vitaminC TEXT,             
    vitaminETotal TEXT,             
    vitaminE1 TEXT,             
    vitaminE2 TEXT,             
    vitaminE3 TEXT,             
    Ca TEXT,             
    P TEXT,             
    K TEXT,             
    Na TEXT,             
    Mg TEXT,             
    Fe TEXT,             
    Zn TEXT,             
    Se TEXT,             
    Cu TEXT,             
    Mn TEXT,             
    remark TEXT,             
    category TEXT,             
    subcategory TEXT,             
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP         
);