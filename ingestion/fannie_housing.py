import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)

# 来自官方 Public API Access Data 指南
TOKEN_URL = (
    "https://auth.pingone.com/"
    "4c2b23f9-52b1-4f8f-aa1f-1d477590770c/as/token"
)
BASE_URL = "https://api.fanniemae.com"


def get_access_token():
    client_id = os.getenv("FANNIE_CLIENT_ID")
    client_secret = os.getenv("FANNIE_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise RuntimeError(
            "请在项目根目录 .env 中填写 "
            "FANNIE_CLIENT_ID 和 FANNIE_CLIENT_SECRET"
        )

    response = requests.post(
        TOKEN_URL,
        # requests 会自动生成官方要求的 Basic 认证头
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials"},
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        },
        timeout=30,
        allow_redirects=False,
    )

    print(f"Token 请求状态：{response.status_code}")

    if response.status_code != 200:
        raise RuntimeError(
            f"获取 Token 失败：HTTP {response.status_code}"
        )

    payload = response.json()
    token = payload.get("access_token")

    if not isinstance(token, str) or not token:
        raise RuntimeError("认证响应中没有有效的 access_token")

    # 不打印或保存 Token
    return token


def fetch_indicator(token, indicator):
    url = (
        f"{BASE_URL}/v1/housing-indicators/"
        f"indicators/{indicator}"
    )

    response = requests.get(
        url,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-public-access-token": token,
        },
        timeout=60,
        allow_redirects=False,
    )

    print(f"{indicator} 请求状态：{response.status_code}")

    if response.status_code != 200:
        raise RuntimeError(
            f"获取指标失败：HTTP {response.status_code}"
        )

    payload = response.json()

    print("响应类型：", type(payload).__name__)

    if isinstance(payload, dict):
        print("最外层字段：", list(payload.keys()))
    elif isinstance(payload, list):
        print("列表长度：", len(payload))
        if payload and isinstance(payload[0], dict):
            print("第一项字段：", list(payload[0].keys()))

    print("响应内容预览：")
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:3000])


    if not isinstance(payload, dict):
        raise RuntimeError("API 返回的 JSON 不是预期的对象")

    series = payload.get("indicatorTimeSeries")

    if series is None:
        series = payload.get("indicators")

    if not isinstance(series, list) or not series:
        raise RuntimeError(
            f"没有找到非空的指标序列，实际字段：{list(payload.keys())}"
        )

    point_count = 0
    for item in series:
        if not isinstance(item, dict):
            raise RuntimeError("指标序列格式不符合预期")
        points = item.get("points") or item.get("timeSeries") or []
        if not isinstance(points, list):
            raise RuntimeError("数据点格式不符合预期")
        point_count += len(points)

    if point_count == 0:
        raise RuntimeError("响应里没有数据点，暂不保存")

    print(f"收到 {len(series)} 个序列、{point_count} 个数据点")
    return payload


def save_raw_json(payload, indicator):
    output_dir = ROOT / "data" / "raw" / "fannie_mae"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    output_file = output_dir / f"{indicator}_{timestamp}.json"

    # 使用 x 模式，避免覆盖已有文件
    with output_file.open("x", encoding="utf-8") as file:
        json.dump(
            payload, file, ensure_ascii=False, indent=2,
            allow_nan=False,
        )

    # 重新读取，确认保存的内容一致
    with output_file.open(encoding="utf-8") as file:
        if json.load(file) != payload:
            raise RuntimeError("保存后的数据校验失败")

    print(f"保存成功：{output_file.relative_to(ROOT)}")

# Housing Indicators API：全部 15 个 indicator
# 住宅开工
# total-housing-starts
#   住宅开工总量
# single-family-1-unit-housing-starts
#   单户住宅开工量
# multifamily-2+units-housing-starts
#   多户住宅开工量（2 个及以上单元）
#
# 房屋销售
# total-home-sales
#   房屋销售总量
# new-single-family-home-sales
#   新建单户住宅销售量
# existing-single-family-condos-coops-home-sales
#   现有单户住宅、公寓及合作公寓销售量
#
# 房价
# median-new-home-price
#   新房价格中位数
# median-existing-home-price
#   现房价格中位数
# federal-housing-finance-agency-purchase-only-house-price-index
#   FHFA 仅购房交易房价指数
#
# 房贷利率
# 30-year-fixed-rate-mortgage
#   30 年期固定利率房贷
# 5-year-adjustable-rate-mortgage
#   5 年期可调整利率房贷
#
# 房贷发放
# single-family-mortgage-originations
#   单户住宅房贷发放总量
# single-family-purchase-mortgage-originations
#   单户住宅购房贷款发放量
# single-family-refinance-mortgage-originations
#   单户住宅再融资贷款发放量
# refinance-share-of-total-single-family-mortgage-originations
#   再融资占单户住宅房贷发放总量的比例



def main():
    indicator = "30-year-fixed-rate-mortgage"
    token = get_access_token()
    payload = fetch_indicator(token, indicator)
    save_raw_json(payload, indicator)


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as error:
        # 不输出可能含认证信息的完整请求或异常内容
        print(f"网络请求失败：{type(error).__name__}")
        raise SystemExit(1)
    except (RuntimeError, ValueError, OSError) as error:
        print(f"运行失败：{error}")
        raise SystemExit(1)
