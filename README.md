# BA-TASK04

TASK04 海龟交易策略课程项目，包含 Python 回测、PDF 报告、行情数据、概念图和交互式网页。

## 在线作品

- 交互式海龟策略实验室：<https://aesir-official.github.io/BA-TASK04/>
- PDF 报告：[胡安TASK4.pdf](./胡安TASK4.pdf)

## 网页功能

- 回测实验室与学习模式双视图
- 华虹公司 `688347`、中际旭创 `300308`、中芯国际 `688981` 三只固定股票
- 唐奇安通道、ATR 风险定仓、金字塔加仓、动态止损和次日开盘成交
- 完整参数调节、净值/回撤/交易信号图和交易明细
- 实验性任意 A 股代码即时查询
- 工作日北京时间 18:00 由 GitHub Actions 更新固定股票数据并部署 Pages

## 主要文件

- `index.html`：交互实验室入口
- `assets/app.js`：浏览器端海龟策略回测引擎
- `scripts/update_market_data.py`：三只固定股票的数据更新脚本
- `task04_turtle_backtest.py`：课程报告使用的 Python 回测脚本
- `data/market_data.json`：网页使用的固定股票行情
- `胡安TASK4.pdf`：课程提交报告

## 本地运行

```bash
python -m http.server 8765 --directory .
```

访问 <http://localhost:8765/>。页面不能直接通过 `file://` 加载本地 JSON。

## 说明

网页中的“入场、加仓、退出”均为当前参数下的规则状态，不构成投资建议。历史回测不保证未来表现。
