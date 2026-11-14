import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "raw" / "fannie_mae"
OUTPUT_DIR = ROOT / "data" / "processed" / "fannie_mae"

COLUMNS = [
    "indicator_name",
    "effective_date",
    "year",
    "quarter",
    "forecast",
    "value",
    "unit",
]


def convert_file(json_file):
    with json_file.open(encoding="utf-8") as file:
        payload = json.load(file)

    # 当前已验证的 Economic Indicators 单指标响应结构
    series_list = payload.get("indicatorTimeSeries")

    if series_list is None:
        series_list = payload.get("indicators")

    if not isinstance(series_list, list) or not series_list:
        raise ValueError("没有非空的 indicatorTimeSeries 列表")

    rows = []

    for series in series_list:
        for point in (
    series.get("points") or series.get("timeSeries") or []
        ):
            rows.append({
                "indicator_name": series["indicatorName"],
                "effective_date": series["effectiveDate"],
                "year": point["year"],
                "quarter": point["quarter"],
                "forecast": point["forecast"],
                "value": point["value"],
                # 部分旧报告没有 unit，保留为空，不擅自补值
                "unit": point.get("unit", ""),
            })

    if not rows:
        raise ValueError("没有可以转换的数据点")

    csv_file = OUTPUT_DIR / f"{json_file.stem}.csv"

    if csv_file.exists():
        print(f"跳过：{csv_file.name} 已存在")
        return

    # x：不覆盖已有文件；utf-8-sig：方便 Excel 打开
    with csv_file.open(
        "x", newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"生成成功：{csv_file.relative_to(ROOT)}")
    print(f"共 {len(rows)} 行")


def main():
    json_files = sorted(INPUT_DIR.glob("*.json"))

    if not json_files:
        print(f"没有找到 JSON，请检查：{INPUT_DIR}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for json_file in json_files:
        try:
            convert_file(json_file)
        except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
            print(f"转换失败：{json_file.name}，原因：{error}")


if __name__ == "__main__":
    main()