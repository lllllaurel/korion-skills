import json
import argparse

standard_file = "assets/daily_standard.json"


def fetch_standard(open_id):
    with open(standard_file, "r", encoding="utf-8") as f:
        standard_data = json.load(f)
    return standard_data[open_id]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--open_id", type=str, required=True)
    args = parser.parse_args()
    print(fetch_standard(args.open_id))
