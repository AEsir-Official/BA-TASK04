from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import akshare as ak
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
STOCK_DIR = DATA_DIR / "stocks"
JSON_PATH = DATA_DIR / "market_data.json"

STOCKS = (
    {"symbol": "688347", "name": "华虹公司", "market": "688347.SH"},
    {"symbol": "300308", "name": "中际旭创", "market": "300308.SZ"},
    {"symbol": "688981", "name": "中芯国际", "market": "688981.SH"},
)

COLUMN_MAP = {
    "日期": "date",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
}
REQUIRED_COLUMNS = ["date", "open", "close", "high", "low", "volume", "amount"]


def fetch_stock(symbol: str, start_date: str, end_date: str) -> tuple[pd.DataFrame, str]:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            raw = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",
            )
            if raw is not None and not raw.empty:
                return normalize(raw), "AkShare / 东方财富前复权日行情"
        except Exception as exc:
            last_error = exc
        time.sleep(2 * (attempt + 1))
    market_symbol = ("sh" if symbol.startswith("6") else "sz") + symbol
    try:
        raw = ak.stock_zh_a_hist_tx(
            symbol=market_symbol,
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
            timeout=30,
        )
        if raw is not None and not raw.empty:
            if "volume" not in raw.columns and "amount" in raw.columns:
                raw = raw.copy()
                raw["volume"] = raw["amount"]
                raw["turnover_amount"] = 0
                raw = raw.rename(columns={"amount": "source_volume", "turnover_amount": "amount"})
                raw["volume"] = raw["source_volume"]
            return normalize(raw), "AkShare / 腾讯前复权日行情（东方财富不可用）"
    except Exception as exc:
        last_error = exc
    raise RuntimeError(f"{symbol} 两个行情接口均获取失败：{last_error}")


def normalize(raw: pd.DataFrame) -> pd.DataFrame:
    frame = raw.rename(columns=COLUMN_MAP).copy()
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"行情缺少字段：{missing}")
    frame = frame[REQUIRED_COLUMNS]
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for column in REQUIRED_COLUMNS[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=REQUIRED_COLUMNS).sort_values("date").drop_duplicates("date")
    frame = frame.reset_index(drop=True)
    if len(frame) < 500:
        raise ValueError(f"有效行情仅 {len(frame)} 行，少于三年回测所需数据")
    if not frame["date"].is_monotonic_increasing or frame["date"].duplicated().any():
        raise ValueError("日期排序或重复检查失败")
    if (frame[["open", "close", "high", "low"]] <= 0).any().any():
        raise ValueError("价格字段包含非正数")
    return frame


def serializable_number(value: float) -> int | float:
    number = float(value)
    return int(number) if number.is_integer() else round(number, 6)


def stock_payload(config: dict[str, str], frame: pd.DataFrame, source: str) -> dict:
    latest = frame["date"].max().normalize()
    visible_start = latest - pd.DateOffset(years=3)
    rows = []
    for record in frame.itertuples(index=False):
        rows.append(
            [
                record.date.strftime("%Y-%m-%d"),
                serializable_number(record.open),
                serializable_number(record.close),
                serializable_number(record.high),
                serializable_number(record.low),
                serializable_number(record.volume),
                serializable_number(record.amount),
            ]
        )
    return {
        **config,
        "source": source,
        "adjustment": "qfq",
        "visible_start": visible_start.strftime("%Y-%m-%d"),
        "latest_trade_date": latest.strftime("%Y-%m-%d"),
        "rows": rows,
    }


def content_fingerprint(payload: dict) -> str:
    stable = {"schema_version": payload["schema_version"], "stocks": payload["stocks"]}
    encoded = json.dumps(stable, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def build_payload() -> tuple[dict, dict[str, pd.DataFrame]]:
    today = date.today()
    fetch_start = today - timedelta(days=3 * 366 + 260)
    frames: dict[str, pd.DataFrame] = {}
    stocks = []
    for config in STOCKS:
        frame, source = fetch_stock(config["symbol"], fetch_start.strftime("%Y%m%d"), today.strftime("%Y%m%d"))
        frames[config["symbol"]] = frame
        stocks.append(stock_payload(config, frame, source))
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "visible_years": 3,
        "row_format": ["date", "open", "close", "high", "low", "volume", "amount"],
        "stocks": stocks,
    }
    payload["content_sha256"] = content_fingerprint(payload)
    return payload, frames


def write_outputs(payload: dict, frames: dict[str, pd.DataFrame], force: bool) -> bool:
    if JSON_PATH.exists() and not force:
        current = json.loads(JSON_PATH.read_text(encoding="utf-8"))
        if current.get("content_sha256") == payload["content_sha256"]:
            print("行情内容未变化，不写入文件。")
            return False
    atomic_write(JSON_PATH, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    STOCK_DIR.mkdir(parents=True, exist_ok=True)
    for symbol, frame in frames.items():
        csv_path = STOCK_DIR / f"{symbol}_qfq_daily.csv"
        temporary = csv_path.with_suffix(".csv.tmp")
        frame.to_csv(temporary, index=False, encoding="utf-8-sig")
        temporary.replace(csv_path)
    print(f"已更新 {len(frames)} 只股票，JSON 指纹：{payload['content_sha256'][:12]}")
    return True


def validate_existing() -> None:
    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["row_format"] == REQUIRED_COLUMNS
    assert len(payload["stocks"]) == len(STOCKS)
    for stock in payload["stocks"]:
        assert len(stock["rows"]) >= 500
        dates = [row[0] for row in stock["rows"]]
        assert dates == sorted(set(dates))
        assert all(len(row) == 7 for row in stock["rows"])
    assert payload["content_sha256"] == content_fingerprint(payload)
    print("现有 market_data.json 验证通过。")


def main() -> None:
    parser = argparse.ArgumentParser(description="更新 TASK04 固定股票池日行情")
    parser.add_argument("--validate", action="store_true", help="只验证现有 JSON")
    parser.add_argument("--force", action="store_true", help="即使内容相同也重新写入")
    args = parser.parse_args()
    if args.validate:
        validate_existing()
        return
    payload, frames = build_payload()
    write_outputs(payload, frames, args.force)


if __name__ == "__main__":
    main()
