(() => {
  "use strict";

  const LOT_SIZE = 100;
  const TRADING_DAYS = 252;
  const UI_FONT = '"Microsoft YaHei","Noto Sans SC",Arial,sans-serif';
  const COLORS = {
    ink: "#20272c", muted: "#687077", line: "#d9d9d3", orange: "#d94d00",
    green: "#237a57", red: "#b7312c", blue: "#2a6f97", paper: "#f5f5f1"
  };
  const PRESETS = {
    classic: { entryWindow: 20, exitWindow: 10, atrWindow: 20, addAtr: 0.5, maxUnits: 4, stopAtr: 2, riskPct: 1 },
    fast: { entryWindow: 10, exitWindow: 5, atrWindow: 14, addAtr: 0.5, maxUnits: 4, stopAtr: 1.5, riskPct: 1 },
    slow: { entryWindow: 55, exitWindow: 20, atrWindow: 20, addAtr: 0.5, maxUnits: 4, stopAtr: 2, riskPct: 1 }
  };
  const PERIOD_LABELS = { "3y": "最近 3 年", "1y": "最近 1 年", "6m": "最近 6 个月", "3m": "最近 3 个月" };
  const state = { dataset: null, stocks: new Map(), activeStock: null, fixedSymbols: [], period: "3y", result: null, customStock: null };
  const charts = {};
  const $ = (id) => document.getElementById(id);

  function number(value, digits = 2) {
    return Number.isFinite(value) ? value.toLocaleString("zh-CN", { minimumFractionDigits: digits, maximumFractionDigits: digits }) : "--";
  }
  function percent(value, digits = 2) {
    return Number.isFinite(value) ? `${(value * 100).toFixed(digits)}%` : "--";
  }
  function compact(value) {
    if (!Number.isFinite(value)) return "--";
    if (Math.abs(value) >= 1e8) return `${(value / 1e8).toFixed(2)}亿`;
    if (Math.abs(value) >= 1e4) return `${(value / 1e4).toFixed(1)}万`;
    return number(value, 0);
  }
  function dateValue(value) { return new Date(`${value}T00:00:00`); }
  function dateOffset(latest, period) {
    const d = new Date(latest.getTime());
    if (period === "3y") d.setFullYear(d.getFullYear() - 3);
    if (period === "1y") d.setFullYear(d.getFullYear() - 1);
    if (period === "6m") d.setMonth(d.getMonth() - 6);
    if (period === "3m") d.setMonth(d.getMonth() - 3);
    return d;
  }
  function safeFinite(value, fallback = null) { return Number.isFinite(value) ? value : fallback; }

  function parseStock(stock) {
    return {
      ...stock,
      rows: stock.rows.map((row) => ({
        date: row[0], open: +row[1], close: +row[2], high: +row[3], low: +row[4], volume: +row[5], amount: +row[6]
      }))
    };
  }

  function rollingExtreme(rows, window, field, mode) {
    const output = new Array(rows.length).fill(null);
    for (let i = window; i < rows.length; i += 1) {
      let value = mode === "max" ? -Infinity : Infinity;
      for (let j = i - window; j < i; j += 1) value = mode === "max" ? Math.max(value, rows[j][field]) : Math.min(value, rows[j][field]);
      output[i] = value;
    }
    return output;
  }

  function calculateAtr(rows, window) {
    const tr = new Array(rows.length).fill(null);
    const atr = new Array(rows.length).fill(null);
    let running = null;
    for (let i = 0; i < rows.length; i += 1) {
      const previousClose = i ? rows[i - 1].close : rows[i].close;
      tr[i] = Math.max(rows[i].high - rows[i].low, Math.abs(rows[i].high - previousClose), Math.abs(rows[i].low - previousClose));
      running = i === 0 ? tr[i] : (running * (window - 1) + tr[i]) / window;
      if (i >= window - 1) atr[i] = running;
    }
    return { tr, atr };
  }

  function unitShares(equity, atr, price, cash, params) {
    if (!(atr > 0) || !(price > 0)) return 0;
    const riskBased = Math.floor((equity * params.riskRate / (params.stopAtr * atr)) / LOT_SIZE) * LOT_SIZE;
    const affordable = Math.floor((cash / (price * (1 + params.commission))) / LOT_SIZE) * LOT_SIZE;
    return Math.max(0, Math.min(riskBased, affordable));
  }

  function collectParams() {
    const params = {};
    document.querySelectorAll("[data-param]").forEach((input) => { params[input.dataset.param] = +input.value; });
    document.querySelectorAll("[data-number]").forEach((input) => { params[input.dataset.number] = +input.value; });
    params.riskRate = params.riskPct / 100;
    params.commission = params.commissionPct / 100;
    params.stampTax = params.stampTaxPct / 100;
    params.slippage = params.slippagePct / 100;
    return params;
  }

  function validateParams(params) {
    if (!(params.exitWindow < params.entryWindow)) return "退出通道周期必须小于入场通道周期。";
    if (!(params.initialCapital >= 10000)) return "初始资金不得低于 10,000 元。";
    if (!(params.riskRate > 0 && params.riskRate <= 0.05)) return "风险预算应在 0.1% 至 5% 之间。";
    return "";
  }

  function runEngine(stock, params, period) {
    const rows = stock.rows;
    const latest = dateValue(rows.at(-1).date);
    const startDate = dateOffset(latest, period);
    let startIndex = rows.findIndex((row) => dateValue(row.date) >= startDate);
    if (startIndex < 0) startIndex = 0;
    const entryHigh = rollingExtreme(rows, params.entryWindow, "high", "max");
    const exitLow = rollingExtreme(rows, params.exitWindow, "low", "min");
    const { atr } = calculateAtr(rows, params.atrWindow);
    let cash = params.initialCapital;
    let shares = 0;
    let units = 0;
    let stopPrice = null;
    let nextAddPrice = null;
    let pending = null;
    let lots = [];
    const trades = [];
    const records = [];
    const actions = [];
    let skippedUnits = 0;

    for (let i = startIndex; i < rows.length; i += 1) {
      const row = rows[i];
      let action = "";
      let actionType = "";
      let actionPrice = null;
      let actionReason = "";

      if (pending) {
        const equityAtOpen = cash + shares * row.open;
        if (pending.action === "entry" || pending.action === "add") {
          const buyPrice = row.open * (1 + params.slippage);
          const quantity = unitShares(equityAtOpen, pending.atr, buyPrice, cash, params);
          if (quantity >= LOT_SIZE) {
            const gross = quantity * buyPrice;
            const commission = gross * params.commission;
            cash -= gross + commission;
            shares += quantity;
            units += 1;
            lots.push({ date: row.date, price: buyPrice, shares: quantity, atr: pending.atr });
            const candidateStop = buyPrice - params.stopAtr * pending.atr;
            stopPrice = stopPrice === null ? candidateStop : Math.max(stopPrice, candidateStop);
            nextAddPrice = buyPrice + params.addAtr * pending.atr;
            action = pending.action === "entry" ? "首次买入" : `加仓至 ${units} 单位`;
            actionType = pending.action;
            actionPrice = buyPrice;
            actionReason = pending.reason;
          } else {
            skippedUnits += 1;
            action = "风险仓位不足 100 股，跳过";
            actionType = "skip";
            actionReason = pending.reason;
          }
        } else if (pending.action === "exit" && shares > 0) {
          const soldShares = shares;
          const sellPrice = row.open * (1 - params.slippage);
          const gross = shares * sellPrice;
          const commission = gross * params.commission;
          const stampTax = gross * params.stampTax;
          cash += gross - commission - stampTax;
          const totalCost = lots.reduce((sum, lot) => sum + lot.price * lot.shares, 0);
          const buyFees = totalCost * params.commission;
          const pnl = gross - commission - stampTax - totalCost - buyFees;
          trades.push({
            entryDate: lots[0]?.date || row.date, exitDate: row.date, units: lots.length, shares: soldShares,
            averageEntry: totalCost / soldShares, exitPrice: sellPrice, pnl,
            returnPct: pnl / (totalCost + buyFees), exitReason: pending.reason
          });
          action = "全部卖出";
          actionType = "exit";
          actionPrice = sellPrice;
          actionReason = pending.reason;
          shares = 0; units = 0; stopPrice = null; nextAddPrice = null; lots = [];
        }
        pending = null;
      }

      const equity = cash + shares * row.close;
      if (shares > 0) {
        if (stopPrice !== null && row.close <= stopPrice) pending = { action: "exit", atr: atr[i], reason: `${params.stopAtr.toFixed(2)} ATR 动态止损`, signalDate: row.date };
        else if (exitLow[i] !== null && row.close < exitLow[i]) pending = { action: "exit", atr: atr[i], reason: `跌破 ${params.exitWindow} 日低点`, signalDate: row.date };
        else if (units < params.maxUnits && nextAddPrice !== null && row.close >= nextAddPrice) pending = { action: "add", atr: atr[i], reason: `上涨 ${params.addAtr.toFixed(2)} ATR 加仓`, signalDate: row.date };
      } else if (entryHigh[i] !== null && row.close > entryHigh[i]) {
        pending = { action: "entry", atr: atr[i], reason: `突破 ${params.entryWindow} 日高点`, signalDate: row.date };
      }

      const record = {
        ...row, sourceIndex: i, entryHigh: entryHigh[i], exitLow: exitLow[i], atr: atr[i], cash, shares, units,
        stopPrice, nextAddPrice, equity, action, actionType, actionPrice, actionReason
      };
      records.push(record);
      if (actionType && actionPrice !== null) actions.push({ date: row.date, type: actionType, price: actionPrice, label: action, reason: actionReason });
    }

    const first = records[0];
    const benchmarkPrice = first.open * (1 + params.slippage);
    const benchmarkShares = params.initialCapital / (benchmarkPrice * (1 + params.commission));
    const benchmarkCash = params.initialCapital - benchmarkShares * benchmarkPrice * (1 + params.commission);
    let peak = -Infinity;
    records.forEach((record, index) => {
      record.strategyReturn = index ? record.equity / records[index - 1].equity - 1 : 0;
      record.strategyNetValue = record.equity / params.initialCapital;
      record.buyHoldEquity = benchmarkCash + benchmarkShares * record.close;
      record.buyHoldNetValue = record.buyHoldEquity / params.initialCapital;
      peak = Math.max(peak, record.equity);
      record.drawdown = record.equity / peak - 1;
    });
    const returns = records.map((record) => record.strategyReturn);
    const mean = returns.reduce((sum, value) => sum + value, 0) / returns.length;
    const variance = returns.length > 1 ? returns.slice(1).reduce((sum, value) => sum + (value - mean) ** 2, 0) / (returns.length - 1) : 0;
    const cumulative = records.at(-1).strategyNetValue - 1;
    const annualized = cumulative > -1 && records.length > 1 ? (1 + cumulative) ** (TRADING_DAYS / (records.length - 1)) - 1 : null;
    const completedWins = trades.filter((trade) => trade.pnl > 0).length;
    const metrics = {
      cumulative, annualized, sharpe: variance > 0 ? Math.sqrt(TRADING_DAYS) * mean / Math.sqrt(variance) : 0,
      mdd: Math.min(...records.map((record) => record.drawdown)),
      winRate: trades.length ? completedWins / trades.length : 0,
      trades: trades.length, stopCount: trades.filter((trade) => trade.exitReason.includes("止损")).length,
      endingEquity: records.at(-1).equity, currentUnits: records.at(-1).units,
      buyHold: records.at(-1).buyHoldNetValue - 1, skippedUnits
    };
    return { stock, params, period, records, trades, actions, metrics, pending, startDate: records[0].date, endDate: records.at(-1).date };
  }

  function renderMetrics(result) {
    const m = result.metrics;
    const entries = [
      ["累计回报", percent(m.cumulative), m.cumulative >= 0 ? "positive" : "negative", "期初至期末"],
      ["年化回报", percent(m.annualized), m.annualized >= 0 ? "positive" : "negative", "按 252 日折算"],
      ["夏普比率", number(m.sharpe), "", "无风险收益率设为 0"],
      ["最大回撤", percent(m.mdd), "negative", "历史峰值至低点"],
      ["胜率", percent(m.winRate), "", "仅统计已平仓交易"],
      ["完成交易", `${m.trades} 笔`, "", `${m.stopCount} 次止损退出`],
      ["期末权益", `${number(m.endingEquity, 0)} 元`, "", `初始 ${number(result.params.initialCapital, 0)} 元`],
      ["当前单位", `${m.currentUnits} / ${result.params.maxUnits}`, "", `${result.records.at(-1).shares} 股`],
      ["买入持有", percent(m.buyHold), m.buyHold >= 0 ? "positive" : "negative", "同期基准"],
      ["跳过单位", `${m.skippedUnits} 次`, "", "风险股数不足一手"],
    ];
    $("metrics").innerHTML = entries.map(([label, value, cls, note]) => `<div class="metric-item"><span>${label}</span><strong class="${cls}">${value}</strong><small>${note}</small></div>`).join("");
  }

  function signalState(result) {
    const latest = result.records.at(-1);
    const pending = result.pending;
    if (pending?.action === "entry") return { cls: "entry", badge: "入场条件已触发", title: "等待下一交易日建立首单位", description: `${latest.date} 收盘价突破 ${result.params.entryWindow} 日上轨。按当前风险预算，下一交易日开盘后重新计算可买股数。` };
    if (pending?.action === "add") return { cls: "add", badge: "加仓条件已触发", title: "已有盈利头寸，等待下一交易日加仓", description: `${latest.date} 收盘价达到下一加仓阈值。加仓后整体止损只会上移，不会向下放松。` };
    if (pending?.action === "exit") return { cls: "exit", badge: "退出条件已触发", title: "等待下一交易日退出全部头寸", description: `${latest.date} 收盘确认“${pending.reason}”。实际开盘跳空可能使成交价偏离理论止损位。` };
    if (latest.shares > 0) return { cls: "hold", badge: "持仓观察", title: `当前持有 ${latest.units} 个风险单位`, description: "尚未触发加仓、止损或反向通道退出条件。继续根据收盘数据更新风险状态。" };
    return { cls: "neutral", badge: "等待突破", title: `尚未突破 ${result.params.entryWindow} 日入场上轨`, description: "当前参数下没有待执行订单。没有信号不代表看空，只表示趋势突破条件尚未成立。" };
  }

  function renderSignal(result) {
    const status = signalState(result);
    const latest = result.records.at(-1);
    const estimated = unitShares(latest.equity, latest.atr, latest.close * (1 + result.params.slippage), latest.cash, result.params);
    const badge = $("signal-badge");
    badge.className = `signal-badge ${status.cls}`;
    badge.textContent = status.badge;
    $("signal-heading").textContent = status.title;
    $("signal-description").textContent = status.description;
    const facts = [
      ["最新收盘价", `${number(latest.close)} 元`], ["入场上轨", latest.entryHigh === null ? "--" : `${number(latest.entryHigh)} 元`],
      ["退出下轨", latest.exitLow === null ? "--" : `${number(latest.exitLow)} 元`], ["ATR", latest.atr === null ? "--" : number(latest.atr)],
      ["当前止损", latest.stopPrice === null ? "--" : `${number(latest.stopPrice)} 元`], ["下一加仓价", latest.nextAddPrice === null ? "--" : `${number(latest.nextAddPrice)} 元`],
      ["估算单位股数", `${estimated} 股`], ["当前现金", `${number(latest.cash, 0)} 元`]
    ];
    $("signal-facts").innerHTML = facts.map(([term, value]) => `<div><dt>${term}</dt><dd>${value}</dd></div>`).join("");
  }

  function axisStyle() {
    return { axisLine: { lineStyle: { color: "#aeb0aa" } }, axisTick: { show: false }, axisLabel: { color: COLORS.muted, fontSize: 10 }, splitLine: { lineStyle: { color: "#ecece7" } } };
  }
  function tooltipBase() {
    return { trigger: "axis", axisPointer: { type: "cross", lineStyle: { color: COLORS.orange } }, backgroundColor: "rgba(32,39,44,.96)", borderWidth: 0, textStyle: { color: "#fff", fontFamily: UI_FONT, fontSize: 11 } };
  }

  function drawCharts(result) {
    const records = result.records;
    const dates = records.map((record) => record.date);
    const recordMap = new Map(records.map((record) => [record.date, record]));
    const buyActions = result.actions.filter((action) => action.type === "entry" || action.type === "add").map((action) => [action.date, action.price, action.label]);
    const exitActions = result.actions.filter((action) => action.type === "exit").map((action) => [action.date, action.price, action.label]);
    const priceTooltip = { ...tooltipBase(), formatter(params) {
      const date = params[0]?.axisValue;
      const row = recordMap.get(date);
      if (!row) return date || "";
      const action = row.action ? `<br><span style="color:#f7a274">动作：${row.action}</span>` : "";
      return `<strong>${row.date}</strong><br>开 ${number(row.open)}　高 ${number(row.high)}<br>低 ${number(row.low)}　收 ${number(row.close)}<br>上轨 ${number(row.entryHigh)}　下轨 ${number(row.exitLow)}<br>ATR ${number(row.atr)}　止损 ${number(row.stopPrice)}<br>成交量 ${compact(row.volume)}${action}`;
    }};
    charts.price.setOption({
      animationDuration: 420, textStyle: { fontFamily: UI_FONT }, tooltip: priceTooltip,
      legend: { top: 12, textStyle: { color: COLORS.muted, fontSize: 10 }, data: ["K线", "入场上轨", "退出下轨", "动态止损", "买入/加仓", "退出"] },
      grid: { left: 62, right: 28, top: 52, bottom: 62 },
      xAxis: { type: "category", data: dates, boundaryGap: true, ...axisStyle() },
      yAxis: { type: "value", scale: true, name: "价格（元）", nameTextStyle: { color: COLORS.muted }, ...axisStyle() },
      dataZoom: [{ type: "inside" }, { type: "slider", height: 20, bottom: 14, borderColor: COLORS.line, fillerColor: "rgba(217,77,0,.12)", handleStyle: { color: COLORS.orange }, textStyle: { color: COLORS.muted } }],
      series: [
        { name: "K线", type: "candlestick", data: records.map((r) => [r.open, r.close, r.low, r.high]), itemStyle: { color: COLORS.red, color0: COLORS.green, borderColor: COLORS.red, borderColor0: COLORS.green } },
        { name: "入场上轨", type: "line", data: records.map((r) => r.entryHigh), showSymbol: false, step: "end", lineStyle: { color: COLORS.orange, width: 1.5 } },
        { name: "退出下轨", type: "line", data: records.map((r) => r.exitLow), showSymbol: false, step: "end", lineStyle: { color: COLORS.green, width: 1.5 } },
        { name: "动态止损", type: "line", data: records.map((r) => r.stopPrice), showSymbol: false, connectNulls: false, lineStyle: { color: COLORS.red, width: 1.2, type: "dashed" } },
        { name: "买入/加仓", type: "scatter", data: buyActions, symbol: "triangle", symbolSize: 13, itemStyle: { color: COLORS.red } },
        { name: "退出", type: "scatter", data: exitActions, symbol: "triangle", symbolRotate: 180, symbolSize: 13, itemStyle: { color: COLORS.green } }
      ]
    }, true);
    charts.equity.setOption({
      animationDuration: 420, textStyle: { fontFamily: UI_FONT }, tooltip: tooltipBase(),
      legend: { top: 10, textStyle: { color: COLORS.muted, fontSize: 10 } }, grid: { left: 58, right: 24, top: 46, bottom: 42 },
      xAxis: { type: "category", data: dates, boundaryGap: false, ...axisStyle() }, yAxis: { type: "value", scale: true, ...axisStyle() },
      series: [
        { name: "海龟策略", type: "line", data: records.map((r) => r.strategyNetValue), showSymbol: false, lineStyle: { color: COLORS.orange, width: 2 } },
        { name: "买入持有", type: "line", data: records.map((r) => r.buyHoldNetValue), showSymbol: false, lineStyle: { color: COLORS.blue, width: 1.6, type: "dashed" } }
      ]
    }, true);
    charts.risk.setOption({
      animationDuration: 420, textStyle: { fontFamily: UI_FONT }, tooltip: tooltipBase(),
      legend: { top: 10, textStyle: { color: COLORS.muted, fontSize: 10 } }, grid: { left: 58, right: 56, top: 46, bottom: 42 },
      xAxis: { type: "category", data: dates, boundaryGap: false, ...axisStyle() },
      yAxis: [
        { type: "value", scale: true, name: "ATR", nameTextStyle: { color: COLORS.muted }, ...axisStyle() },
        { type: "value", max: 0, name: "回撤", nameTextStyle: { color: COLORS.muted }, axisLabel: { color: COLORS.muted, formatter: (value) => `${(value * 100).toFixed(0)}%` }, splitLine: { show: false } }
      ],
      series: [
        { name: "ATR", type: "line", data: records.map((r) => r.atr), showSymbol: false, lineStyle: { color: "#d39b10", width: 1.5 }, areaStyle: { color: "rgba(211,155,16,.16)" } },
        { name: "策略回撤", type: "line", yAxisIndex: 1, data: records.map((r) => r.drawdown), showSymbol: false, lineStyle: { color: COLORS.green, width: 1.4 }, areaStyle: { color: "rgba(35,122,87,.12)" } }
      ]
    }, true);
  }

  function renderTrades(result) {
    $("trade-summary").textContent = `${result.trades.length} 笔已完成交易 · ${result.metrics.stopCount} 次止损退出`;
    const body = $("trade-table-body");
    if (!result.trades.length) {
      body.innerHTML = '<tr class="empty-row"><td colspan="9">当前区间没有已完成交易，可能仍在持仓或尚未出现完整信号。</td></tr>';
      return;
    }
    body.innerHTML = [...result.trades].reverse().map((trade) => `<tr>
      <td>${trade.entryDate}</td><td>${trade.exitDate}</td><td>${trade.units}</td><td>${trade.shares}</td>
      <td>${number(trade.averageEntry)}</td><td>${number(trade.exitPrice)}</td>
      <td class="${trade.pnl >= 0 ? "positive" : "negative"}">${number(trade.pnl, 0)}</td>
      <td class="${trade.returnPct >= 0 ? "positive" : "negative"}">${percent(trade.returnPct)}</td><td>${trade.exitReason}</td>
    </tr>`).join("");
  }

  function renderContext(result) {
    $("active-stock").textContent = `${result.stock.name} ${result.stock.market}`;
    $("active-range").textContent = `${result.startDate} 至 ${result.endDate}`;
    $("latest-date").textContent = result.stock.latest_trade_date;
    $("data-source").textContent = result.stock.source;
    $("period-output").textContent = PERIOD_LABELS[state.period];
  }

  function runAndRender() {
    if (!state.activeStock) return;
    const params = collectParams();
    const error = validateParams(params);
    $("parameter-error").textContent = error;
    if (error) return;
    try {
      const result = runEngine(state.activeStock, params, state.period);
      state.result = result;
      renderContext(result); renderMetrics(result); renderSignal(result); drawCharts(result); renderTrades(result);
    } catch (errorValue) {
      $("parameter-error").textContent = `回测失败：${errorValue.message}`;
    }
  }

  function renderStockButtons() {
    const container = $("stock-buttons");
    const fixed = state.fixedSymbols.map((symbol) => state.stocks.get(symbol));
    if (state.customStock) fixed.push(state.customStock);
    container.innerHTML = "";
    fixed.forEach((stock) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `stock-button${state.activeStock?.symbol === stock.symbol ? " active" : ""}`;
      const strong = document.createElement("strong"); strong.textContent = stock.name;
      const span = document.createElement("span"); span.textContent = stock.market;
      button.append(strong, span);
      button.addEventListener("click", () => { state.activeStock = stock; renderStockButtons(); runAndRender(); });
      container.appendChild(button);
    });
  }

  function updateRangeOutputs() {
    const formats = {
      entryWindow: (v) => `${v}`, exitWindow: (v) => `${v}`, atrWindow: (v) => `${v}`,
      addAtr: (v) => `${(+v).toFixed(2)} ATR`, maxUnits: (v) => `${v}`,
      stopAtr: (v) => `${(+v).toFixed(2)} ATR`, riskPct: (v) => `${(+v).toFixed(1)}%`
    };
    document.querySelectorAll("[data-param]").forEach((input) => { document.querySelector(`[data-output="${input.dataset.param}"]`).textContent = formats[input.dataset.param](input.value); });
  }

  function applyPreset(name) {
    const preset = PRESETS[name];
    Object.entries(preset).forEach(([key, value]) => { const input = document.querySelector(`[data-param="${key}"]`); if (input) input.value = value; });
    document.querySelectorAll("[data-preset]").forEach((button) => button.classList.toggle("active", button.dataset.preset === name));
    $("preset-output").textContent = name === "classic" ? "经典" : name === "fast" ? "短线" : "长线";
    updateRangeOutputs(); runAndRender();
  }

  function jsonp(url, timeout = 15000) {
    return new Promise((resolve, reject) => {
      const callback = `__task04_jsonp_${Date.now()}_${Math.floor(Math.random() * 10000)}`;
      const script = document.createElement("script");
      const timer = window.setTimeout(() => cleanup(new Error("查询超时")), timeout);
      function cleanup(error, value) {
        window.clearTimeout(timer); delete window[callback]; script.remove();
        error ? reject(error) : resolve(value);
      }
      window[callback] = (payload) => cleanup(null, payload);
      script.onerror = () => cleanup(new Error("第三方数据接口不可用"));
      script.src = `${url}${url.includes("?") ? "&" : "?"}cb=${callback}`;
      document.head.appendChild(script);
    });
  }

  async function loadCustomStock(symbol) {
    const status = $("custom-stock-status");
    if (!/^\d{6}$/.test(symbol)) { status.className = "field-note error"; status.textContent = "请输入有效的 6 位 A 股代码。"; return; }
    if (state.stocks.has(symbol)) { state.activeStock = state.stocks.get(symbol); renderStockButtons(); runAndRender(); status.className = "field-note success"; status.textContent = "已切换到固定股票数据。"; return; }
    status.className = "field-note"; status.textContent = `正在临时查询 ${symbol}…`;
    const secid = `${symbol.startsWith("6") ? "1" : "0"}.${symbol}`;
    const latest = new Date(); const begin = new Date(); begin.setFullYear(latest.getFullYear() - 4);
    const ymd = (d) => `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}`;
    const url = `https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=${secid}&klt=101&fqt=1&beg=${ymd(begin)}&end=20500101&lmt=1500&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57`;
    try {
      const payload = await jsonp(url);
      const data = payload?.data;
      if (!data?.klines?.length) throw new Error("未返回可用行情");
      const rows = data.klines.map((line) => line.split(",")).map((r) => [r[0], +r[1], +r[2], +r[3], +r[4], +r[5], +r[6]]).filter((r) => r.slice(1, 5).every((value) => value > 0));
      const latestDate = rows.at(-1)[0];
      const custom = parseStock({ symbol, name: data.name || `A股 ${symbol}`, market: `${symbol}.${symbol.startsWith("6") ? "SH" : "SZ"}`, source: "东方财富浏览器即时查询（实验性）", adjustment: "qfq", visible_start: rows[0][0], latest_trade_date: latestDate, rows });
      state.customStock = custom; state.activeStock = custom; renderStockButtons(); runAndRender();
      status.className = "field-note success"; status.textContent = `已临时加载 ${custom.name}，不会写入仓库。`;
    } catch (error) {
      status.className = "field-note error"; status.textContent = `加载失败：${error.message}。固定股票仍可正常使用。`;
    }
  }

  function switchMode(mode) {
    document.querySelectorAll(".mode-button").forEach((button) => button.classList.toggle("active", button.dataset.mode === mode));
    $("lab-mode").classList.toggle("active", mode === "lab");
    $("learn-mode").classList.toggle("active", mode === "learn");
    if (mode === "lab") window.setTimeout(() => Object.values(charts).forEach((chart) => chart.resize()), 40);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function bindEvents() {
    document.querySelectorAll(".mode-button").forEach((button) => button.addEventListener("click", () => switchMode(button.dataset.mode)));
    document.querySelectorAll("[data-switch-to-lab]").forEach((button) => button.addEventListener("click", () => switchMode("lab")));
    document.querySelectorAll("[data-param]").forEach((input) => input.addEventListener("input", updateRangeOutputs));
    document.querySelectorAll("[data-preset]").forEach((button) => button.addEventListener("click", () => applyPreset(button.dataset.preset)));
    document.querySelectorAll("[data-period]").forEach((button) => button.addEventListener("click", () => {
      state.period = button.dataset.period;
      document.querySelectorAll("[data-period]").forEach((item) => item.classList.toggle("active", item === button));
      runAndRender();
    }));
    $("run-backtest").addEventListener("click", runAndRender);
    const submitCustomStock = (event) => { event?.preventDefault(); loadCustomStock($("custom-stock").value.trim()); };
    $("custom-stock-form").addEventListener("submit", submitCustomStock);
    $("custom-stock-load").addEventListener("click", submitCustomStock);
    $("custom-stock").addEventListener("input", (event) => {
      const value = event.target.value.trim();
      const status = $("custom-stock-status");
      if (!value) {
        status.className = "field-note";
        status.textContent = "第三方接口不可用时，固定股票仍可正常使用。";
      } else if (!/^\d{6}$/.test(value)) {
        status.className = "field-note error";
        status.textContent = "请输入完整的 6 位 A 股代码。";
      } else {
        status.className = "field-note success";
        status.textContent = "代码格式有效，点击“加载”开始临时查询。";
      }
    });
    window.addEventListener("resize", () => Object.values(charts).forEach((chart) => chart.resize()));
  }

  async function init() {
    try {
      if (!window.echarts) throw new Error("本地 ECharts 资源加载失败");
      const response = await fetch("data/market_data.json", { cache: "no-store" });
      if (!response.ok) throw new Error(`行情 JSON 加载失败（${response.status}）`);
      state.dataset = await response.json();
      state.dataset.stocks.forEach((raw) => { const stock = parseStock(raw); state.stocks.set(stock.symbol, stock); state.fixedSymbols.push(stock.symbol); });
      state.activeStock = state.stocks.get("688347") || state.stocks.values().next().value;
      charts.price = echarts.init($("price-chart")); charts.equity = echarts.init($("equity-chart")); charts.risk = echarts.init($("risk-chart"));
      bindEvents(); updateRangeOutputs(); renderStockButtons(); runAndRender();
      $("loading-overlay").classList.add("hidden");
    } catch (error) {
      $("loading-overlay").innerHTML = `<p>页面初始化失败：${error.message}</p><p>请通过本地服务器或 GitHub Pages 打开。</p>`;
    }
  }

  init();
})();
