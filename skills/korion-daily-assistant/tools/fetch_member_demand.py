import json
import argparse


def get_user_data(open_id_target, key):
    with open("user_nutrition.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    for user in data["用户列表"]:
        if user["open_id"] == open_id_target:
            if key == "all":
                return json.dumps(user, ensure_ascii=False, indent=2)
            if key not in user:
                return "{}"
            return json.dumps(user[key], ensure_ascii=False, indent=2)
    return "{}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--open_id", type=str, help="用户open_id")
    parser.add_argument(
        "--field",
        type=str,
        default="all",
        help="目标内容: 个人信息|每日营养需求|推荐食物|all",
    )
    args = parser.parse_args()

    field = args.field
    open_id = args.open_id

    # 调用查询
    res = get_user_data(open_id_target=open_id, key=field)
    print(res)
