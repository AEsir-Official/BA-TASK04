from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
FIGURES = ROOT / "figures"
CONCEPTS = ROOT / "concepts"
OUTPUT = ROOT / "胡安TASK4.pdf"

PAGE_W, PAGE_H = A4
MARGIN_X = 1.75 * cm
MARGIN_TOP = 1.65 * cm
MARGIN_BOTTOM = 1.55 * cm
CONTENT_W = PAGE_W - 2 * MARGIN_X

ORANGE = colors.HexColor("#d94d00")
CHARCOAL = colors.HexColor("#20272c")
MID_GRAY = colors.HexColor("#626a70")
LIGHT_GRAY = colors.HexColor("#f3f3ef")
LINE_GRAY = colors.HexColor("#d7d8d3")
GREEN = colors.HexColor("#2f6f3e")
RED = colors.HexColor("#b22f2a")


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont("SimSun", r"C:\Windows\Fonts\simsun.ttc", subfontIndex=0))
    pdfmetrics.registerFont(TTFont("MicrosoftYaHei", r"C:\Windows\Fonts\msyh.ttc", subfontIndex=0))
    pdfmetrics.registerFont(TTFont("MicrosoftYaHeiBold", r"C:\Windows\Fonts\msyhbd.ttc", subfontIndex=0))


def build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "body": ParagraphStyle(
            "BodyCN",
            parent=base["BodyText"],
            fontName="SimSun",
            fontSize=10.5,
            leading=15.75,
            firstLineIndent=21,
            alignment=TA_JUSTIFY,
            wordWrap="CJK",
            spaceBefore=0,
            spaceAfter=0,
            textColor=CHARCOAL,
        ),
        "body_no_indent": ParagraphStyle(
            "BodyNoIndentCN",
            parent=base["BodyText"],
            fontName="SimSun",
            fontSize=10.5,
            leading=15.75,
            alignment=TA_JUSTIFY,
            wordWrap="CJK",
            spaceBefore=0,
            spaceAfter=0,
            textColor=CHARCOAL,
        ),
        "h1": ParagraphStyle(
            "Heading1CN",
            parent=base["Heading1"],
            fontName="MicrosoftYaHeiBold",
            fontSize=17,
            leading=22,
            textColor=CHARCOAL,
            spaceBefore=0,
            spaceAfter=7,
        ),
        "h2": ParagraphStyle(
            "Heading2CN",
            parent=base["Heading2"],
            fontName="MicrosoftYaHeiBold",
            fontSize=12.5,
            leading=17,
            textColor=ORANGE,
            spaceBefore=5,
            spaceAfter=3,
        ),
        "formula": ParagraphStyle(
            "FormulaCN",
            parent=base["BodyText"],
            fontName="MicrosoftYaHei",
            fontSize=10.5,
            leading=17,
            alignment=TA_CENTER,
            textColor=CHARCOAL,
            wordWrap="CJK",
        ),
        "caption": ParagraphStyle(
            "CaptionCN",
            parent=base["BodyText"],
            fontName="SimSun",
            fontSize=9,
            leading=13,
            alignment=TA_CENTER,
            textColor=MID_GRAY,
            wordWrap="CJK",
            spaceBefore=3,
            spaceAfter=3,
        ),
        "small": ParagraphStyle(
            "SmallCN",
            parent=base["BodyText"],
            fontName="SimSun",
            fontSize=8.4,
            leading=12,
            alignment=TA_LEFT,
            wordWrap="CJK",
            textColor=MID_GRAY,
        ),
        "cover_title": ParagraphStyle(
            "CoverTitle",
            parent=base["Title"],
            fontName="MicrosoftYaHeiBold",
            fontSize=28,
            leading=39,
            alignment=TA_LEFT,
            textColor=colors.white,
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle",
            parent=base["BodyText"],
            fontName="MicrosoftYaHei",
            fontSize=14,
            leading=22,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#f5c2a5"),
        ),
        "cover_meta": ParagraphStyle(
            "CoverMeta",
            parent=base["BodyText"],
            fontName="SimSun",
            fontSize=11,
            leading=20,
            alignment=TA_LEFT,
            textColor=CHARCOAL,
        ),
    }


def page_decor(canvas, doc) -> None:
    page = canvas.getPageNumber()
    canvas.saveState()
    if page == 1:
        canvas.setFillColor(CHARCOAL)
        canvas.rect(0, PAGE_H - 10.7 * cm, PAGE_W, 10.7 * cm, stroke=0, fill=1)
        canvas.setFillColor(ORANGE)
        canvas.rect(0, PAGE_H - 10.9 * cm, PAGE_W, 0.2 * cm, stroke=0, fill=1)
        canvas.setFillColor(colors.HexColor("#e9eae6"))
        canvas.circle(PAGE_W - 3.0 * cm, PAGE_H - 4.0 * cm, 1.25 * cm, stroke=0, fill=1)
        canvas.setFillColor(ORANGE)
        canvas.circle(PAGE_W - 3.0 * cm, PAGE_H - 4.0 * cm, 0.86 * cm, stroke=0, fill=1)
        canvas.setFillColor(CHARCOAL)
        canvas.circle(PAGE_W - 3.0 * cm, PAGE_H - 4.0 * cm, 0.46 * cm, stroke=0, fill=1)
    else:
        canvas.setStrokeColor(ORANGE)
        canvas.setLineWidth(1.2)
        canvas.line(MARGIN_X, PAGE_H - 1.15 * cm, PAGE_W - MARGIN_X, PAGE_H - 1.15 * cm)
        canvas.setFont("MicrosoftYaHei", 8.5)
        canvas.setFillColor(MID_GRAY)
        canvas.drawString(MARGIN_X, PAGE_H - 0.92 * cm, "TASK04 | 华虹公司海龟策略回测报告")
        canvas.drawRightString(PAGE_W - MARGIN_X, 0.85 * cm, f"{page:02d}")
        canvas.setStrokeColor(LINE_GRAY)
        canvas.setLineWidth(0.6)
        canvas.line(MARGIN_X, 1.12 * cm, PAGE_W - MARGIN_X, 1.12 * cm)
    canvas.restoreState()


def formula_box(text: str, styles: dict[str, ParagraphStyle]) -> Table:
    table = Table([[Paragraph(text, styles["formula"])]], colWidths=[CONTENT_W])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GRAY),
                ("BOX", (0, 0), (-1, -1), 0.8, ORANGE),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def scaled_image(path: Path, width: float) -> Image:
    source = path
    if path.parent == FIGURES:
        normalized_dir = ROOT / "tmp" / "pdfs" / "pdf_images"
        normalized_dir.mkdir(parents=True, exist_ok=True)
        source = normalized_dir / path.name
        with PILImage.open(path) as original:
            rgb = original.convert("RGB")
            if rgb.width > 1800:
                height = round(rgb.height * 1800 / rgb.width)
                rgb = rgb.resize((1800, height), PILImage.Resampling.LANCZOS)
            rgb.save(source, format="PNG", optimize=True)
    image = Image(str(source))
    image_width = image.imageWidth
    image_height = image.imageHeight
    image.drawWidth = width
    image.drawHeight = width * image_height / image_width
    return image


def metric_cards(metrics: pd.Series, styles: dict[str, ParagraphStyle]) -> Table:
    labels = ["累计回报", "最大回撤", "夏普比率", "完成交易", "胜率", "期末权益"]
    values = [
        f"{metrics['累计回报']:.2%}",
        f"{metrics['最大回撤']:.2%}",
        f"{metrics['夏普比率']:.2f}",
        f"{int(metrics['完成交易次数'])} 次",
        f"{metrics['胜率']:.0%}",
        f"{metrics['期末权益']:,.0f} 元",
    ]
    cells = []
    for label, value in zip(labels, values):
        cells.append(Paragraph(f"<font name='MicrosoftYaHei' size='8.5' color='#626a70'>{label}</font><br/><font name='MicrosoftYaHeiBold' size='15' color='#20272c'>{value}</font>", styles["body_no_indent"]))
    table = Table([cells[:3], cells[3:]], colWidths=[CONTENT_W / 3] * 3, rowHeights=[1.55 * cm, 1.55 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GRAY),
                ("GRID", (0, 0), (-1, -1), 0.6, colors.white),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def data_table(rows: list[list], widths: list[float], styles: dict[str, ParagraphStyle], header: bool = True) -> Table:
    converted = []
    for row_index, row in enumerate(rows):
        converted.append(
            [
                Paragraph(
                    str(value),
                    ParagraphStyle(
                        f"table-{row_index}",
                        parent=styles["small"],
                        fontName="MicrosoftYaHeiBold" if header and row_index == 0 else "SimSun",
                        fontSize=8.2,
                        leading=11.5,
                        textColor=colors.white if header and row_index == 0 else CHARCOAL,
                        alignment=TA_CENTER,
                        wordWrap="CJK",
                    ),
                )
                for value in row
            ]
        )
    table = Table(converted, colWidths=widths, repeatRows=1 if header else 0)
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.55, LINE_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), CHARCOAL),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
            ]
        )
    table.setStyle(TableStyle(commands))
    return table


def build_pdf() -> None:
    register_fonts()
    styles = build_styles()
    metadata = json.loads((DATA / "task04_metadata.json").read_text(encoding="utf-8"))
    metrics_df = pd.read_csv(DATA / "task04_metrics_summary.csv")
    main = metrics_df.iloc[0]
    trades = pd.read_csv(DATA / "task04_trades.csv")
    main_trades = trades[trades["参数"].str.contains("主策略")]

    doc = BaseDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=MARGIN_X,
        rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
        title="TASK04 华虹公司海龟策略回测报告",
        author="胡安",
        subject="Python 海龟交易策略实现与回测",
    )
    frame = Frame(MARGIN_X, MARGIN_BOTTOM, CONTENT_W, PAGE_H - MARGIN_TOP - MARGIN_BOTTOM, id="normal")
    doc.addPageTemplates([PageTemplate(id="report", frames=[frame], onPage=page_decor)])
    story = []

    # Page 1: cover
    story.extend(
        [
            Spacer(1, 1.35 * cm),
            Paragraph("TASK04", styles["cover_subtitle"]),
            Spacer(1, 0.2 * cm),
            Paragraph("华虹公司海龟策略<br/>设计、实现与回测", styles["cover_title"]),
            Spacer(1, 0.35 * cm),
            Paragraph("唐奇安通道 · ATR 风险定仓 · 金字塔加仓 · 动态止损", styles["cover_subtitle"]),
            Spacer(1, 5.2 * cm),
            Paragraph("课程：量化交易工作坊", styles["cover_meta"]),
            Paragraph("姓名：胡安", styles["cover_meta"]),
            Paragraph(f"证券：华虹公司 688347.SH", styles["cover_meta"]),
            Paragraph(f"回测区间：{metadata['report_start']} 至 {metadata['report_end']}", styles["cover_meta"]),
            Paragraph(f"数据来源：{metadata['data_source']}", styles["cover_meta"]),
            PageBreak(),
        ]
    )

    # Page 2: executive summary
    story.extend(
        [
            Paragraph("摘要与主要结论", styles["h1"]),
            Paragraph("本报告以华虹公司 688347.SH 为研究对象，使用 AkShare 获取前复权日行情，并在最新交易日前一年的样本上实现完整的做多海龟策略。主策略采用 20 日高点突破入场、10 日低点离场、20 日 ATR、2 ATR 动态止损、0.5 ATR 金字塔加仓以及风险单位定仓。所有信号均在收盘后确认，并在下一交易日开盘成交，从而避免未来函数。", styles["body"]),
            Spacer(1, 0.25 * cm),
            metric_cards(main, styles),
            Spacer(1, 0.25 * cm),
            Paragraph("结果表明，主策略累计回报达到 137.02%，最大回撤为 -15.28%，年化夏普比率为 2.44。同期买入持有回报约为 600.61%，显著高于策略回报。原因并不是海龟策略失效，而是华虹公司在样本后段出现极强单边上涨；风险定仓、分批加仓与通道退出限制了持仓速度和资金利用率，却显著压低了回撤。", styles["body"]),
            Paragraph("本样本中只完成两笔主策略交易，且期末仍持有 1,900 股，因此 100% 的已平仓胜率不能被解释为稳定胜率。单一股票、单一年份和趋势显著的样本也不足以证明策略具有普遍盈利能力。报告将重点分析规则如何控制风险，而不是把历史收益直接外推为未来表现。", styles["body"]),
            Paragraph("报告结构", styles["h2"]),
            data_table(
                [
                    ["部分", "内容"],
                    ["第一部分", "策略思想、通道、TR/ATR、风险定仓、加仓、止损与绩效指标公式"],
                    ["第二部分", "华虹公司数据、回测实现、交易信号、净值回撤、参数比较与应用心得"],
                ],
                [3.2 * cm, CONTENT_W - 3.2 * cm],
                styles,
            ),
            PageBreak(),
        ]
    )

    # Page 3
    story.extend(
        [
            Paragraph("第一部分  海龟策略与指标公式", styles["h1"]),
            Paragraph("1. 海龟策略的核心思想与优势", styles["h2"]),
            Paragraph("海龟交易法则是一套机械化趋势跟踪系统。它不预测顶部和底部，而是用价格突破确认趋势、用 ATR 统一波动尺度、用风险预算确定仓位、用盈利加仓扩大有效头寸，并用动态止损和反向通道退出。核心原则是“截断亏损，让利润奔跑”。", styles["body"]),
            Paragraph("关键优势包括：规则明确，便于程序化执行；仓位与波动挂钩，使不同价格和波动水平具有可比较风险；止损、退出和总单位数预先设定，减少临场情绪干扰；适合捕捉少数持续时间较长的大趋势。其代价是在震荡市场中会出现连续假突破、小额亏损和浮盈回吐。", styles["body"]),
            Spacer(1, 0.18 * cm),
            scaled_image(CONCEPTS / "fig1_turtle_workflow.png", CONTENT_W),
            Paragraph("图 1 解读：完整系统从市场与数据质量开始，经过突破识别、ATR 测量和风险定仓后才允许建仓；盈利时最多加至四个单位，随后由止损或反向通道退出，最终使用回报、回撤与夏普比率评价。", styles["caption"]),
            PageBreak(),
        ]
    )

    # Page 4
    story.extend(
        [
            Paragraph("2. 高低点通道与突破信号", styles["h1"]),
            Paragraph("唐奇安通道由过去 N 个交易日的最高价和最低价构成。本报告主策略使用 20 日最高价作为入场上轨，使用 10 日最低价作为趋势退出下轨。计算时整体向后移动一个交易日，确保第 t 日信号只使用 t-1 日及以前的信息。", styles["body"]),
            formula_box("HH20(t-1) = max[H(t-20), ..., H(t-1)]<br/>LL10(t-1) = min[L(t-10), ..., L(t-1)]<br/>入场：C(t) &gt; HH20(t-1)；退出：C(t) &lt; LL10(t-1)", styles),
            Spacer(1, 0.15 * cm),
            scaled_image(CONCEPTS / "fig2_donchian_channel.png", CONTENT_W),
            Paragraph("图 2 解读：通道突破的价值在于等待价格证明趋势，而不是主观猜测趋势。20/10 参数响应较快，能够较早进入，但在横盘阶段也更容易反复触发；55/20 参数更稳健，却可能错过趋势初段。", styles["caption"]),
            PageBreak(),
        ]
    )

    # Page 5
    story.extend(
        [
            Paragraph("3. 真实波幅与平均真实波幅", styles["h1"]),
            Paragraph("真实波幅 TR 同时考虑日内最高价与最低价的差、最高价与前收盘价的跳空距离、最低价与前收盘价的跳空距离。ATR 是 TR 的平滑平均，用于衡量资产在当前阶段的正常波动水平。本报告采用经典的 20 日 Wilder 平滑。", styles["body"]),
            formula_box("TR(t) = max{H(t)-L(t), |H(t)-C(t-1)|, |L(t)-C(t-1)|}<br/>ATR20(t) = [19 × ATR20(t-1) + TR(t)] / 20", styles),
            Spacer(1, 0.15 * cm),
            scaled_image(CONCEPTS / "fig3_tr_atr.png", CONTENT_W),
            Paragraph("图 3 解读：若只计算 H-L，就会忽略隔夜跳空。TR 选择三种距离中的最大值，使波动测量更完整。ATR 越大，单位仓位应越小且止损距离越宽；ATR 越小，则可以在相同风险预算下持有更多股数。", styles["caption"]),
            PageBreak(),
        ]
    )

    # Page 6
    story.extend(
        [
            Paragraph("4. 风险定仓与金字塔加仓", styles["h1"]),
            Paragraph("本报告采用保守风险口径：单个单位从入场价跌至 2 ATR 止损位时，理论损失不超过当时账户权益的 1%。A 股以 100 股为一手，理论股数向下取整；不足 100 股则跳过，避免为了成交而突破风险预算。", styles["body"]),
            formula_box("风险预算 = 账户权益 × 1%<br/>单位股数 = floor{风险预算 / [2 × ATR × 100]} × 100", styles),
            Paragraph("首次突破建立一个单位。随后价格每相对最近成交价上涨 0.5 ATR，再增加一个单位，最多持有四个单位。该规则只在已有头寸盈利时加仓，不在价格下跌时摊低成本。", styles["body"]),
            scaled_image(CONCEPTS / "fig5_position_pyramid.png", CONTENT_W),
            Paragraph("图 5 解读：风险过滤器先决定每个单位的股数，再允许逐级加仓。随着 ATR 增大，单位股数会下降；即使价格继续上涨，最多四个单位的上限仍限制了单一股票的风险暴露。", styles["caption"]),
            PageBreak(),
        ]
    )

    # Page 7
    story.extend(
        [
            Paragraph("5. ATR 动态止损与趋势退出", styles["h1"]),
            Paragraph("首次建仓后，初始止损设在成交价下方 2 ATR。每次加仓后，以最新加仓价减去当时 2 ATR 形成候选止损，并与原止损取较大值。因此止损只能上移，不能因波动扩大而向下放松。若收盘价跌破止损或 10 日最低价，则在下一交易日开盘全部卖出。", styles["body"]),
            formula_box("初始止损 = 入场价 - 2 × ATR<br/>更新止损 = max(原止损, 最新加仓价 - 2 × ATR)", styles),
            Spacer(1, 0.12 * cm),
            scaled_image(CONCEPTS / "fig4_atr_dynamic_stop.png", CONTENT_W),
            Paragraph("图 4 解读：波动较大时，2 ATR 对应的价格距离自动放宽，减少正常噪声造成的误卖；波动较小时止损距离收紧。动态止损负责限制异常逆向运动，反向通道则负责判断趋势是否结束，两者共同构成退出系统。", styles["caption"]),
            PageBreak(),
        ]
    )

    # Page 8
    story.extend(
        [
            Paragraph("6. 策略评价指标及公式", styles["h1"]),
            Paragraph("累计回报衡量从回测起点到终点的总收益。它直观但不反映收益路径和风险，因此必须与最大回撤和夏普比率联合使用。", styles["body"]),
            formula_box("累计回报 = V(T) / V(0) - 1", styles),
            Paragraph("最大回撤 MDD 衡量净值从历史高点到随后低点的最大跌幅，是投资者在样本期间可能经历的最严重账面损失。数值越接近 0，路径风险越低。", styles["body"]),
            formula_box("DD(t) = V(t) / max[V(0), ..., V(t)] - 1<br/>MDD = min DD(t)", styles),
            Paragraph("夏普比率衡量单位总波动所获得的超额收益。本报告日频无风险收益率设为 0，以 252 个交易日年化。夏普越高通常表示风险调整后表现越好，但非正态收益、样本过短或交易过少都会削弱其解释力。", styles["body"]),
            formula_box("Sharpe = √252 × mean(r_d) / std(r_d)", styles),
            Paragraph("辅助指标", styles["h2"]),
            data_table(
                [
                    ["指标", "计算口径", "作用"],
                    ["完成交易次数", "已完成买入至全部卖出的交易周期", "判断样本是否足够"],
                    ["胜率", "盈利的已平仓交易数 / 已平仓交易数", "描述命中率，不代表盈亏比"],
                    ["买入持有回报", "期初一次买入并持有至期末", "作为最简单基准"],
                ],
                [3.2 * cm, 6.0 * cm, CONTENT_W - 9.2 * cm],
                styles,
            ),
            Paragraph("指标解释边界：海龟系统通常依靠少数大盈利覆盖多次小亏损，因此胜率可能较低；本报告主策略完成交易仅两次，任何胜率结论都应谨慎。", styles["body"]),
            PageBreak(),
        ]
    )

    # Page 9
    story.extend(
        [
            Paragraph("第二部分  华虹公司实证分析", styles["h1"]),
            Paragraph("7. 数据、参数与回测流程", styles["h2"]),
            Paragraph(f"数据通过 AkShare 的 stock_zh_a_hist 接口重新获取，证券代码为 688347，采用前复权日线。原始数据从 {metadata['fetch_start']} 开始，用于指标预热；正式统计区间为 {metadata['report_start']} 至 {metadata['report_end']}，共 {int(main['交易日数'])} 个交易日。日期按升序排列，无重复交易日，开盘、最高、最低、收盘、成交量和成交额核心字段完整。", styles["body"]),
            data_table(
                [
                    ["模块", "设定"],
                    ["主通道", "20日最高价突破入场；10日最低价跌破退出"],
                    ["波动指标", "20日 Wilder ATR；初始及更新止损距离为2ATR"],
                    ["仓位", "初始权益500,000元；单单位风险1%；100股整手；最多4单位"],
                    ["加仓", "相对最近成交价每上涨0.5ATR增加1单位"],
                    ["成交", "收盘确认信号；下一交易日开盘成交；仅做多"],
                    ["成本", "佣金0.03%；卖出印花税0.10%；双边滑点0.05%"],
                ],
                [4.0 * cm, CONTENT_W - 4.0 * cm],
                styles,
            ),
            Paragraph("程序执行顺序", styles["h2"]),
            Paragraph("第一步，在每个交易日开盘执行前一交易日收盘产生的挂起指令；第二步，按当日收盘价计算账户权益；第三步，检查止损、通道退出、加仓和首次突破；第四步，仅将符合条件的指令安排到下一交易日。该顺序明确隔离“信号产生”和“订单成交”，避免在同一根日 K 线中使用尚未知晓的信息。", styles["body"]),
            Paragraph("A 股适配", styles["h2"]),
            Paragraph("由于采用次日开盘成交，当日买入最早也只能在下一交易日收盘产生卖出信号，再下一交易日开盘卖出，满足 T+1 的最低持有约束。回测仍无法完整模拟涨跌停封单、停牌和真实冲击成本，因此结果属于规则研究，不是可直接执行的收益承诺。", styles["body"]),
            PageBreak(),
        ]
    )

    # Page 10
    story.extend(
        [
            Paragraph("8. 通道、交易信号与交易记录", styles["h1"]),
            scaled_image(FIGURES / "fig6_channel_signals.png", CONTENT_W),
            Paragraph("图 6 解读：主策略在样本早期突破 20 日上轨后完成首次建仓，并在趋势延续过程中逐级加仓。卖出点由 10 日低点跌破或 2 ATR 止损触发。后段股价快速上涨时，策略再次持仓并在期末保持未平仓状态。", styles["caption"]),
            data_table(
                [["入场日期", "退出日期", "单位", "股数", "均价", "退出价", "净损益", "退出原因"]]
                + [
                    [
                        pd.to_datetime(row["entry_date"]).strftime("%Y-%m-%d"),
                        pd.to_datetime(row["exit_date"]).strftime("%Y-%m-%d"),
                        int(row["units"]),
                        int(row["shares"]),
                        f"{row['average_entry']:.2f}",
                        f"{row['exit_price']:.2f}",
                        f"{row['pnl']:,.0f}",
                        row["exit_reason"],
                    ]
                    for _, row in main_trades.iterrows()
                ],
                [2.0 * cm, 2.0 * cm, 1.1 * cm, 1.25 * cm, 1.35 * cm, 1.35 * cm, 1.7 * cm, CONTENT_W - 11.75 * cm],
                styles,
            ),
            Paragraph("第一笔已平仓交易从 2025-07-25 持有至 2025-11-12，四个单位合计实现约 24.32 万元净利润，是样本收益的主要来源。第二笔交易由 2 ATR 止损退出，盈利较小，说明动态止损既能保护头寸，也可能在震荡阶段较早结束交易。", styles["body"]),
            PageBreak(),
        ]
    )

    # Page 11
    story.extend(
        [
            Paragraph("9. ATR 与动态止损分析", styles["h1"]),
            scaled_image(FIGURES / "fig7_atr_stop.png", CONTENT_W),
            Paragraph("图 7 解读：样本后段股价快速上行，ATR 同步显著扩大。风险定仓因 ATR 上升而降低单位股数，止损距离则按 2 ATR 放宽；加仓完成后，整体止损只上移，不随 ATR 扩大向下调整。", styles["caption"]),
            Paragraph("ATR 的双重作用", styles["h2"]),
            Paragraph("ATR 同时进入仓位分母和止损距离。波动上升时，单个单位股数下降，而价格止损距离扩大，二者共同把不同波动阶段转换为近似统一的账户风险。相比固定买入股数和固定百分比止损，这种方法更能适应价格水平和波动状态的变化。", styles["body"]),
            Paragraph("日线模型的限制", styles["h2"]),
            Paragraph("本报告统一使用收盘确认和次日开盘成交，没有根据当日最高价、最低价模拟盘中突破。这样牺牲了部分原始海龟规则的盘中敏感度，却避免日线数据无法判断“先突破还是先止损”的路径问题。真实交易若使用盘中订单，需要分钟级数据重新验证滑点、成交顺序和涨跌停约束。", styles["body"]),
            PageBreak(),
        ]
    )

    # Page 12
    story.extend(
        [
            Paragraph("10. 净值、回撤与基准比较", styles["h1"]),
            scaled_image(FIGURES / "fig8_equity_drawdown.png", CONTENT_W),
            Paragraph("图 8 解读：主策略净值在第一轮趋势中快速上升，之后经历回撤和横盘，再在后段行情中恢复上行。最大回撤为 -15.28%，明显低于买入持有在剧烈价格波动中可能承受的路径风险。", styles["caption"]),
            metric_cards(main, styles),
            Spacer(1, 0.2 * cm),
            Paragraph("主策略期末权益为 1,185,114 元，累计回报 137.02%。同期买入持有回报约 600.61%，反映华虹公司在样本期经历了极端强势上涨。海龟策略未全仓持有，而是按风险预算分批建仓，因此上涨捕获率较低。这一差距揭示了趋势系统的核心权衡：降低暴露和回撤的同时，也会在单边牛市中落后于全仓基准。", styles["body"]),
            Paragraph("夏普比率 2.44 表明该样本内单位日波动对应的平均收益较高，但样本仅 233 个交易日、完成交易仅两次，且期末头寸尚未平仓。该数值不能作为长期稳定性的证据，应在更长历史和多股票组合上继续检验。", styles["body"]),
            PageBreak(),
        ]
    )

    # Page 13
    story.extend(
        [
            Paragraph("11. 通道参数敏感性", styles["h1"]),
            scaled_image(FIGURES / "fig9_parameter_comparison.png", CONTENT_W),
            Paragraph("图 9 解读：20/10 参数在本样本中累计回报最高、最大回撤最低、夏普比率最高。更长通道确认更慢，减少了早期趋势暴露，并在该单边上涨样本中表现落后。", styles["caption"]),
            data_table(
                [["参数", "累计回报", "最大回撤", "夏普", "完成交易", "胜率", "期末持仓"]]
                + [
                    [
                        row["参数"],
                        f"{row['累计回报']:.2%}",
                        f"{row['最大回撤']:.2%}",
                        f"{row['夏普比率']:.2f}",
                        int(row["完成交易次数"]),
                        f"{row['胜率']:.0%}",
                        f"{int(row['期末持仓股数'])}股",
                    ]
                    for _, row in metrics_df.iterrows()
                ],
                [3.1 * cm, 2.2 * cm, 2.2 * cm, 1.8 * cm, 2.0 * cm, 1.6 * cm, CONTENT_W - 12.9 * cm],
                styles,
            ),
            Paragraph("参数比较不能被理解为“20/10 永远最佳”。三组结果都来自同一股票和同一年份，选择表现最好的参数会引入样本内优化偏差。20/10 更适合趋势启动快、持续性强且流动性良好的品种；55/20 更强调确认，在噪声较多的市场可能减少假突破，但会付出更晚入场的代价。", styles["body"]),
            PageBreak(),
        ]
    )

    # Page 14
    story.extend(
        [
            Paragraph("12. 适用场景、使用心得与局限", styles["h1"]),
            Paragraph("适用场景", styles["h2"]),
            Paragraph("海龟法则更适合流动性好、能够形成中长期趋势、交易成本较低的股票或多资产组合。其收益结构通常是多次小亏与少数大盈利并存，因此需要稳定执行、足够长的观察期以及跨行业分散。对长期横盘、频繁跳空、成交受限或基本面事件高度集中的股票，应降低预期并增加流动性和事件过滤。", styles["body"]),
            Paragraph("本次应用心得", styles["h2"]),
            Paragraph("指标本身不是完整策略，通道、ATR、仓位、加仓、止损和执行时点必须形成一致规则。风险定仓能够显著降低高波动阶段的单位股数，但 100 股整手会使小账户无法精确控制风险。单边上涨时全仓持有可能远胜风险控制策略，但这不代表其路径风险更低。参数越敏感越容易捕捉早期趋势，也越容易在震荡中付出交易成本。", styles["body"]),
            Paragraph("局限与改进", styles["h2"]),
            Paragraph("本报告只研究华虹公司一只股票和一年的数据；未模拟涨跌停封单、停牌、最小佣金、过户费和分钟级成交顺序；夏普比率以零无风险收益率计算；参数比较属于样本内分析。后续可扩展到多股票组合、滚动样本外检验、趋势过滤、成交量过滤和参数稳定性热力图，并使用分钟数据检验盘中突破订单。", styles["body"]),
            Paragraph("结论", styles["h2"]),
            Paragraph("华虹公司样本显示，20/10 海龟策略在控制约 15.28% 最大回撤的同时取得 137.02% 累计回报，但明显落后于极端上涨环境中的买入持有。真正值得保留的不是某一组历史最优参数，而是可复现的信号、无未来函数的成交逻辑、与 ATR 挂钩的风险仓位以及严格执行的退出纪律。", styles["body"]),
            Paragraph("参考资料", styles["h2"]),
            Paragraph("[1] TASK04/knowledge044.md，《海龟交易法则：完整交易系统总结》。", styles["small"]),
            Paragraph("[2] Curtis Faith, <link href='https://c.mql5.com/3/131/Curtis_Faith_-_Original_Turtle_Rules.pdf' color='#d94d00'>The Original Turtle Trading Rules</link>。", styles["small"]),
            Paragraph("[3] AKShare 官方文档，<link href='https://akshare.akfamily.xyz/data/stock/stock.html' color='#d94d00'>A 股历史行情 stock_zh_a_hist</link>。", styles["small"]),
            Paragraph("[4] T. Cheung et al., <link href='https://www.mdpi.com/1911-8074/12/2/96' color='#d94d00'>AdTurtle: An Advanced Turtle Trading System</link>, Journal of Risk and Financial Management, 2019。", styles["small"]),
            Paragraph("注：本报告仅用于课程研究与 Python 编程练习，不构成任何投资建议。", styles["small"]),
        ]
    )

    doc.build(story)
    print(f"Generated: {OUTPUT}")


if __name__ == "__main__":
    build_pdf()
