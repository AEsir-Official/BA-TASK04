from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
CONCEPTS = ROOT / "concepts"
FONT_REGULAR = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")

CHARCOAL = "#20272c"
ORANGE = "#d94d00"
GREEN = "#2f6f3e"
RED = "#bd2c25"
BLUE = "#2d6eb3"
WHITE = "#ffffff"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size=size)


def header(draw: ImageDraw.ImageDraw, width: int, title: str, subtitle: str) -> None:
    draw.rounded_rectangle((28, 22, width - 28, 98), radius=18, fill=(255, 255, 255, 240), outline=ORANGE, width=3)
    draw.text((55, 35), title, fill=CHARCOAL, font=font(34, True))
    title_width = draw.textlength(title, font=font(34, True))
    draw.text((72 + title_width, 46), subtitle, fill="#596168", font=font(19))


def centered(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, size: int = 25, color: str = CHARCOAL, bold: bool = False, spacing: int = 8) -> None:
    fnt = font(size, bold)
    bounds = draw.multiline_textbbox((0, 0), text, font=fnt, spacing=spacing, align="center")
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    x = box[0] + (box[2] - box[0] - width) / 2
    y = box[1] + (box[3] - box[1] - height) / 2
    draw.multiline_text((x, y), text, font=fnt, fill=color, spacing=spacing, align="center")


def pill(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, color: str) -> None:
    fnt = font(21, True)
    width = int(draw.textlength(text, font=fnt)) + 30
    x, y = xy
    draw.rounded_rectangle((x, y, x + width, y + 42), radius=18, fill=(255, 255, 255, 235), outline=color, width=3)
    draw.text((x + 15, y + 7), text, fill=color, font=fnt)


def save_workflow() -> None:
    image = Image.open(CONCEPTS / "raw_workflow.png").convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    header(draw, image.width, "图 1  海龟策略完整交易流程", "规则化趋势跟踪：识别、定仓、执行、退出、评估")
    labels = [
        "01  市场筛选\n流动性与数据质量",
        "02  通道突破\n收盘确认趋势",
        "03  ATR衡量\n统一波动尺度",
        "04  风险定仓\n单单位风险1%",
        "05  盈利加仓\n每0.5ATR增加",
        "06  动态止损\n统一止损只上移",
        "07  绩效评估\n回报、回撤、夏普",
    ]
    centers = [155, 384, 610, 834, 1058, 1283, 1510]
    for center_x, label in zip(centers, labels):
        centered(draw, (center_x - 105, 610, center_x + 105, 735), label, size=18, bold=True, spacing=6)
    image.convert("RGB").save(CONCEPTS / "fig1_turtle_workflow.png", quality=95)


def save_donchian() -> None:
    image = Image.open(CONCEPTS / "raw_donchian.png").convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    header(draw, image.width, "图 2  唐奇安高低点通道", "通道必须整体向后移动一日，避免使用当日未知信息")
    centered(draw, (40, 130, 325, 450), "上轨\n过去20个交易日\n最高价的最大值", size=27, color=ORANGE, bold=True)
    centered(draw, (40, 620, 325, 840), "下轨\n过去10个交易日\n最低价的最小值", size=27, color=GREEN, bold=True)
    centered(draw, (1390, 245, 1638, 675), "入场条件\n\nC(t) > HH20(t-1)\n\n收盘确认后\n下一交易日开盘买入", size=24, bold=True)
    image.convert("RGB").save(CONCEPTS / "fig2_donchian_channel.png", quality=95)


def save_atr() -> None:
    image = Image.open(CONCEPTS / "raw_atr.png").convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    header(draw, image.width, "图 3  真实波幅 TR 与 ATR", "把日内振幅和隔夜跳空统一纳入波动测量")
    pill(draw, (165, 205), "H - L", ORANGE)
    pill(draw, (55, 560), "|L - C_prev|", RED)
    pill(draw, (520, 180), "|H - C_prev|", BLUE)
    centered(draw, (1075, 535, 1610, 815), "TR = max(H-L, |H-C_prev|, |L-C_prev|)\n\nATR20(t) = [19×ATR20(t-1) + TR(t)] / 20\n\nATR越大，正常波动范围越宽", size=24, bold=True, spacing=12)
    image.convert("RGB").save(CONCEPTS / "fig3_tr_atr.png", quality=95)


def save_stop() -> None:
    image = Image.open(CONCEPTS / "raw_stop.png").convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    header(draw, image.width, "图 4  ATR 动态止损系统", "止损距离随波动自适应，并在加仓后只上移、不下调")
    centered(draw, (60, 205, 325, 675), "波动较大\n\nATR上升\n止损距离自动放宽\n减少正常噪声误伤", size=25, color=ORANGE, bold=True)
    centered(draw, (1360, 205, 1610, 675), "波动较小\n\nATR下降\n止损距离自动收紧\n保护已有利润", size=25, color=GREEN, bold=True)
    draw.rounded_rectangle((365, 735, 1305, 850), radius=16, fill=(255, 255, 255, 238), outline=ORANGE, width=2)
    centered(draw, (390, 748, 1280, 838), "初始止损价 = 入场价 - 2×ATR\n加仓后止损 = max(原止损, 最新加仓价 - 2×ATR)", size=23, color=CHARCOAL, bold=True, spacing=10)
    image.convert("RGB").save(CONCEPTS / "fig4_atr_dynamic_stop.png", quality=95)


def save_pyramid() -> None:
    image = Image.open(CONCEPTS / "raw_pyramid.png").convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    header(draw, image.width, "图 5  风险定仓与金字塔加仓", "先按2ATR止损控制单位风险，再只对盈利头寸逐级加仓")
    centered(draw, (75, 165, 350, 210), "账户资金", size=25, color=WHITE, bold=True)
    centered(draw, (70, 565, 355, 645), "账户权益 500,000元\n单单位风险预算 = 权益 × 1%", size=20, color=CHARCOAL, bold=True, spacing=6)
    centered(draw, (470, 155, 695, 290), "风险过滤器\n单位股数向下取整至100股", size=20, color=GREEN, bold=True)
    centered(draw, (935, 610, 1295, 655), "单位1：首次突破", size=18, color=CHARCOAL, bold=True)
    centered(draw, (1115, 496, 1392, 545), "单位2：+0.5ATR", size=17, color=CHARCOAL, bold=True)
    centered(draw, (1195, 380, 1398, 435), "单位3：+1.0ATR", size=15, color=CHARCOAL, bold=True)
    centered(draw, (1218, 184, 1326, 228), "单位4", size=15, color=CHARCOAL, bold=True)
    pill(draw, (1330, 235), "+1.5ATR", ORANGE)
    bottom = [
        ((110, 850, 400, 910), "只在盈利时加仓"),
        ((470, 850, 765, 910), "最多4个风险单位"),
        ((840, 850, 1135, 910), "不足100股则跳过"),
        ((1215, 850, 1505, 910), "止损随加仓上移"),
    ]
    for box, label in bottom:
        centered(draw, box, label, size=19, color=GREEN, bold=True)
    image.convert("RGB").save(CONCEPTS / "fig5_position_pyramid.png", quality=95)


def main() -> None:
    save_workflow()
    save_donchian()
    save_atr()
    save_stop()
    save_pyramid()
    print("Concept infographics composed.")


if __name__ == "__main__":
    main()
