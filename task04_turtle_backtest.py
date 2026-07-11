from __future__ import annotations

import json
import math
import shutil
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import akshare as ak
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
FIGURE_DIR = ROOT / "figures"

SYMBOL = "688347"
SECURITY_NAME = "华虹公司"
INITIAL_CAPITAL = 500_000.0
RISK_PER_UNIT = 0.01
ATR_PERIOD = 20
STOP_ATR = 2.0
ADD_ATR = 0.5
MAX_UNITS = 4
COMMISSION_RATE = 0.0003
STAMP_TAX_RATE = 0.001
SLIPPAGE_RATE = 0.0005
LOT_SIZE = 100


@dataclass(frozen=True)
class StrategyConfig:
    entry_period: int
    exit_period: int
    label: str


CONFIGS = [
    StrategyConfig(20, 10, "20/10（主策略）"),
    StrategyConfig(30, 15, "30/15"),
    StrategyConfig(55, 20, "55/20"),
]


def configure_plotting() -> None:
    candidates = [
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
    ]
    from matplotlib import font_manager

    for path in candidates:
        if path.exists():
            font_manager.fontManager.addfont(str(path))
            family = font_manager.FontProperties(fname=str(path)).get_name()
            plt.rcParams["font.sans-serif"] = [family]
            break
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 140
    plt.rcParams["savefig.dpi"] = 220


def fetch_market_data() -> tuple[pd.DataFrame, str]:
    today = date.today()
    fetch_start = today - timedelta(days=650)
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            raw = ak.stock_zh_a_hist(
                symbol=SYMBOL,
                period="daily",
                start_date=fetch_start.strftime("%Y%m%d"),
                end_date=today.strftime("%Y%m%d"),
                adjust="qfq",
            )
            if raw is not None and not raw.empty:
                return normalize_market_data(raw), "AkShare stock_zh_a_hist（前复权）"
        except Exception as exc:  # Network providers occasionally reset connections.
            last_error = exc
            time.sleep(1.5 * (attempt + 1))

    fallback = ROOT.parent / "TASK03" / "data" / "688347_10_30_akshare_qfq_full.csv"
    if not fallback.exists():
        raise RuntimeError(f"AkShare 获取失败，且未找到回退数据：{last_error}")
    cached = pd.read_csv(fallback)
    return normalize_market_data(cached), "TASK03 AkShare 前复权缓存（在线获取失败）"


def normalize_market_data(raw: pd.DataFrame) -> pd.DataFrame:
    mapping = {
        "日期": "date",
        "股票代码": "symbol",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
        "振幅": "amplitude",
        "涨跌幅": "pct_change",
        "涨跌额": "change",
        "换手率": "turnover",
    }
    df = raw.rename(columns=mapping).copy()
    if "date" not in df.columns and "日期" not in raw.columns:
        raise ValueError("行情数据缺少日期字段")
    required = ["date", "open", "close", "high", "low", "volume", "amount"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"行情数据缺少字段：{missing}")
    df["date"] = pd.to_datetime(df["date"])
    for column in required[1:]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=required).sort_values("date").drop_duplicates("date").reset_index(drop=True)
    df["symbol"] = SYMBOL
    df["name"] = SECURITY_NAME
    return df


def add_indicators(df: pd.DataFrame, config: StrategyConfig) -> pd.DataFrame:
    out = df.copy()
    previous_close = out["close"].shift(1)
    tr = pd.concat(
        [
            out["high"] - out["low"],
            (out["high"] - previous_close).abs(),
            (out["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out["tr"] = tr
    out["atr20"] = tr.ewm(alpha=1 / ATR_PERIOD, adjust=False, min_periods=ATR_PERIOD).mean()
    out["entry_high"] = out["high"].rolling(config.entry_period).max().shift(1)
    out["exit_low"] = out["low"].rolling(config.exit_period).min().shift(1)
    return out


def unit_shares(equity: float, atr: float, price: float, cash: float) -> int:
    if not np.isfinite(atr) or atr <= 0 or price <= 0:
        return 0
    risk_based = math.floor((equity * RISK_PER_UNIT / (STOP_ATR * atr)) / LOT_SIZE) * LOT_SIZE
    affordable = math.floor((cash / (price * (1 + COMMISSION_RATE))) / LOT_SIZE) * LOT_SIZE
    return max(0, min(risk_based, affordable))


def run_backtest(source: pd.DataFrame, config: StrategyConfig, report_start: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    df = add_indicators(source, config)
    cash = INITIAL_CAPITAL
    shares = 0
    units = 0
    stop_price = np.nan
    next_add_price = np.nan
    pending: dict | None = None
    lots: list[dict] = []
    trades: list[dict] = []
    skipped_units = 0
    records: list[dict] = []

    for _, row in df.iterrows():
        action_text = ""
        execution_price = np.nan
        signal_reason = ""

        if pending is not None:
            action = pending["action"]
            atr_for_order = float(pending["atr"])
            open_price = float(row["open"])
            equity_at_open = cash + shares * open_price

            if action in {"entry", "add"}:
                buy_price = open_price * (1 + SLIPPAGE_RATE)
                quantity = unit_shares(equity_at_open, atr_for_order, buy_price, cash)
                if quantity >= LOT_SIZE:
                    gross = quantity * buy_price
                    commission = gross * COMMISSION_RATE
                    cash -= gross + commission
                    shares += quantity
                    units += 1
                    lots.append({"date": row["date"], "price": buy_price, "shares": quantity, "atr": atr_for_order})
                    candidate_stop = buy_price - STOP_ATR * atr_for_order
                    stop_price = candidate_stop if not np.isfinite(stop_price) else max(stop_price, candidate_stop)
                    next_add_price = buy_price + ADD_ATR * atr_for_order
                    action_text = "首次买入" if action == "entry" else f"加仓至{units}单位"
                    execution_price = buy_price
                    signal_reason = pending["reason"]
                else:
                    skipped_units += 1
                    action_text = "风险仓位不足100股，跳过"
                    signal_reason = pending["reason"]

            elif action == "exit" and shares > 0:
                sell_price = open_price * (1 - SLIPPAGE_RATE)
                gross = shares * sell_price
                commission = gross * COMMISSION_RATE
                stamp_tax = gross * STAMP_TAX_RATE
                cash += gross - commission - stamp_tax
                total_cost = sum(lot["price"] * lot["shares"] for lot in lots)
                buy_fees = total_cost * COMMISSION_RATE
                pnl = gross - commission - stamp_tax - total_cost - buy_fees
                trades.append(
                    {
                        "entry_date": lots[0]["date"] if lots else pd.NaT,
                        "exit_date": row["date"],
                        "units": len(lots),
                        "shares": shares,
                        "average_entry": total_cost / shares if shares else np.nan,
                        "exit_price": sell_price,
                        "pnl": pnl,
                        "return_pct": pnl / (total_cost + buy_fees) if total_cost else np.nan,
                        "exit_reason": pending["reason"],
                    }
                )
                action_text = "全部卖出"
                execution_price = sell_price
                signal_reason = pending["reason"]
                shares = 0
                units = 0
                stop_price = np.nan
                next_add_price = np.nan
                lots = []
            pending = None

        close = float(row["close"])
        equity = cash + shares * close
        if row["date"] >= report_start:
            if shares > 0:
                if np.isfinite(stop_price) and close <= stop_price:
                    pending = {"action": "exit", "atr": row["atr20"], "reason": "2ATR动态止损"}
                elif np.isfinite(row["exit_low"]) and close < row["exit_low"]:
                    pending = {"action": "exit", "atr": row["atr20"], "reason": f"跌破{config.exit_period}日低点"}
                elif units < MAX_UNITS and np.isfinite(next_add_price) and close >= next_add_price:
                    pending = {"action": "add", "atr": row["atr20"], "reason": "上涨0.5ATR加仓"}
            elif np.isfinite(row["entry_high"]) and close > row["entry_high"]:
                pending = {"action": "entry", "atr": row["atr20"], "reason": f"突破{config.entry_period}日高点"}

        records.append(
            {
                **row.to_dict(),
                "cash": cash,
                "shares": shares,
                "units": units,
                "stop_price": stop_price,
                "next_add_price": next_add_price,
                "equity": equity,
                "action": action_text,
                "execution_price": execution_price,
                "action_reason": signal_reason,
            }
        )

    result = pd.DataFrame(records)
    report = result[result["date"] >= report_start].copy().reset_index(drop=True)
    report["strategy_return"] = report["equity"].pct_change().fillna(0.0)
    report["strategy_net_value"] = report["equity"] / INITIAL_CAPITAL
    report["running_peak"] = report["equity"].cummax()
    report["drawdown"] = report["equity"] / report["running_peak"] - 1

    first_open = float(report.iloc[0]["open"])
    benchmark_buy = first_open * (1 + SLIPPAGE_RATE)
    benchmark_shares = INITIAL_CAPITAL / (benchmark_buy * (1 + COMMISSION_RATE))
    benchmark_cash = INITIAL_CAPITAL - benchmark_shares * benchmark_buy * (1 + COMMISSION_RATE)
    report["buy_hold_equity"] = benchmark_cash + benchmark_shares * report["close"]
    report["buy_hold_net_value"] = report["buy_hold_equity"] / INITIAL_CAPITAL

    closed = pd.DataFrame(trades)
    daily = report["strategy_return"]
    volatility = daily.std(ddof=1)
    sharpe = np.sqrt(252) * daily.mean() / volatility if volatility and np.isfinite(volatility) else 0.0
    cumulative = report.iloc[-1]["strategy_net_value"] - 1
    benchmark_return = report.iloc[-1]["buy_hold_net_value"] - 1
    mdd = report["drawdown"].min()
    metrics = {
        "参数": config.label,
        "入场周期": config.entry_period,
        "离场周期": config.exit_period,
        "回测开始": report.iloc[0]["date"].strftime("%Y-%m-%d"),
        "回测结束": report.iloc[-1]["date"].strftime("%Y-%m-%d"),
        "交易日数": len(report),
        "累计回报": float(cumulative),
        "最大回撤": float(mdd),
        "夏普比率": float(sharpe),
        "买入持有回报": float(benchmark_return),
        "完成交易次数": int(len(closed)),
        "胜率": float((closed["pnl"] > 0).mean()) if not closed.empty else 0.0,
        "期末权益": float(report.iloc[-1]["equity"]),
        "跳过单位次数": int(skipped_units),
        "期末持仓股数": int(report.iloc[-1]["shares"]),
    }
    return report, closed, metrics


def style_axis(ax, title: str, ylabel: str = "") -> None:
    ax.set_facecolor("#fbfbf8")
    ax.grid(True, color="#d8d8d2", linewidth=0.7, alpha=0.65)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.tick_params(labelsize=8)


def plot_channel_signals(report: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11.3, 5.7))
    ax.plot(report["date"], report["close"], color="#242424", linewidth=1.35, label="收盘价")
    ax.plot(report["date"], report["entry_high"], color="#d9482b", linewidth=1.1, label="20日上轨")
    ax.plot(report["date"], report["exit_low"], color="#237a57", linewidth=1.1, label="10日下轨")
    buys = report[report["action"].isin(["首次买入", "加仓至2单位", "加仓至3单位", "加仓至4单位"])]
    sells = report[report["action"] == "全部卖出"]
    ax.scatter(buys["date"], buys["execution_price"], marker="^", s=58, color="#148f5a", label="买入/加仓", zorder=5)
    ax.scatter(sells["date"], sells["execution_price"], marker="v", s=58, color="#c7362f", label="卖出", zorder=5)
    style_axis(ax, "图 6  华虹公司海龟策略通道与交易信号", "价格（元）")
    ax.legend(ncol=5, fontsize=8, frameon=False, loc="upper left")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "fig6_channel_signals.png", bbox_inches="tight")
    plt.close(fig)


def plot_atr_stop(report: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(11.3, 6.5), sharex=True, gridspec_kw={"height_ratios": [2.1, 1]})
    axes[0].plot(report["date"], report["close"], color="#242424", linewidth=1.25, label="收盘价")
    axes[0].plot(report["date"], report["stop_price"], color="#d9482b", linewidth=1.25, label="动态止损价")
    style_axis(axes[0], "图 7  ATR 与动态止损轨迹", "价格（元）")
    axes[0].legend(frameon=False, fontsize=8, loc="upper left")
    axes[1].fill_between(report["date"], report["atr20"], color="#e4a11b", alpha=0.45)
    axes[1].plot(report["date"], report["atr20"], color="#a05b00", linewidth=1.05)
    style_axis(axes[1], "20日 ATR", "ATR（元）")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "fig7_atr_stop.png", bbox_inches="tight")
    plt.close(fig)


def plot_equity_drawdown(report: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(11.3, 6.7), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    axes[0].plot(report["date"], report["strategy_net_value"], color="#d9482b", linewidth=1.5, label="海龟策略")
    axes[0].plot(report["date"], report["buy_hold_net_value"], color="#2a6f97", linewidth=1.25, label="买入持有")
    style_axis(axes[0], "图 8  策略净值、买入持有与回撤", "净值")
    axes[0].legend(frameon=False, fontsize=8, loc="upper left")
    axes[1].fill_between(report["date"], report["drawdown"] * 100, 0, color="#b3261e", alpha=0.55)
    style_axis(axes[1], "策略回撤", "回撤（%）")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "fig8_equity_drawdown.png", bbox_inches="tight")
    plt.close(fig)


def plot_parameter_comparison(metrics_df: pd.DataFrame) -> None:
    labels = metrics_df["参数"].tolist()
    fig, axes = plt.subplots(1, 3, figsize=(11.3, 4.4))
    values = [
        (metrics_df["累计回报"] * 100, "累计回报（%）", "#d9482b"),
        (metrics_df["最大回撤"] * 100, "最大回撤（%）", "#2a6f97"),
        (metrics_df["夏普比率"], "夏普比率", "#d39b10"),
    ]
    for ax, (series, title, color) in zip(axes, values):
        bars = ax.bar(labels, series, color=color, width=0.58)
        style_axis(ax, title)
        ax.tick_params(axis="x", rotation=12)
        for bar, value in zip(bars, series):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{value:.2f}", ha="center", va="bottom" if value >= 0 else "top", fontsize=8)
    fig.suptitle("图 9  华虹公司不同通道参数回测比较", fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "fig9_parameter_comparison.png", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    configure_plotting()

    market, source_label = fetch_market_data()
    latest = market["date"].max().normalize()
    report_start = latest - pd.DateOffset(years=1)
    market.to_csv(DATA_DIR / "688347_akshare_qfq_full.csv", index=False, encoding="utf-8-sig")

    all_metrics: list[dict] = []
    all_trades: list[pd.DataFrame] = []
    reports: dict[str, pd.DataFrame] = {}
    for config in CONFIGS:
        report, trades, metrics = run_backtest(market, config, report_start)
        key = f"{config.entry_period}_{config.exit_period}"
        reports[key] = report
        all_metrics.append(metrics)
        report.to_csv(DATA_DIR / f"688347_turtle_{key}_daily.csv", index=False, encoding="utf-8-sig")
        if not trades.empty:
            trades.insert(0, "参数", config.label)
            all_trades.append(trades)

    metrics_df = pd.DataFrame(all_metrics)
    metrics_df.to_csv(DATA_DIR / "task04_metrics_summary.csv", index=False, encoding="utf-8-sig")
    trades_df = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    trades_df.to_csv(DATA_DIR / "task04_trades.csv", index=False, encoding="utf-8-sig")

    main_report = reports["20_10"]
    plot_channel_signals(main_report)
    plot_atr_stop(main_report)
    plot_equity_drawdown(main_report)
    plot_parameter_comparison(metrics_df)

    metadata = {
        "symbol": SYMBOL,
        "name": SECURITY_NAME,
        "data_source": source_label,
        "adjustment": "前复权",
        "fetch_start": market.iloc[0]["date"].strftime("%Y-%m-%d"),
        "latest_trade_date": latest.strftime("%Y-%m-%d"),
        "report_start": main_report.iloc[0]["date"].strftime("%Y-%m-%d"),
        "report_end": main_report.iloc[-1]["date"].strftime("%Y-%m-%d"),
        "initial_capital": INITIAL_CAPITAL,
        "risk_per_unit": RISK_PER_UNIT,
        "commission_rate": COMMISSION_RATE,
        "stamp_tax_rate": STAMP_TAX_RATE,
        "slippage_rate": SLIPPAGE_RATE,
        "lot_size": LOT_SIZE,
    }
    (DATA_DIR / "task04_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"metadata": metadata, "metrics": all_metrics}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
