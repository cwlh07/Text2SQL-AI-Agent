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
        f"{BASE_URL}/v1/economic-forecasts/"
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

    if not isinstance(series, list) or not series:
        raise RuntimeError(
            "响应中没有非空的 indicatorTimeSeries 列表"
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


# Economic Indicators API 的全部 16 个 indicator 选项, replace the indicator: 
# gross-domestic-product
# personal-consumption-expenditures
# residential-fixed-investment
# business-fixed-investment
# government-consumption-and-investment
# net-exports
# change-in-business-inventories

# consumer-price-index
# core-consumer-price-index-excl-food-and-energy
# personal-chain-expenditures-chain-price-index
# core-personal-chain-expenditures-chain-price-index-excl-food-and-energy

# unemployment-rate
# employment-total-nonfarm
#   非农就业总量

# federal-funds-rate
# 1-year-treasury-note-yield
# 10-year-treasury-note-yield

def main():
    indicator = "unemployment-rate"
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
