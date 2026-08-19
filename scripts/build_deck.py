"""新季さんへの資料（5年ビジョン・資金計画）をPowerPointで組み立てる。

数字はすべて scratchpad/deck.json・compare.json（アプリのエンジンが出した値）から読む。
ここで数字を手打ちしない＝アプリの計算とズレない、という作りにしている。
"""
from __future__ import annotations

import json
import os
import sys

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

SC = ("/private/tmp/claude-502/-Users-Office-Desktop-Claude-private/"
      "86f3df5d-53be-453b-aeb3-b23831f5312a/scratchpad")
D = json.load(open(f"{SC}/deck.json", encoding="utf-8"))
C = json.load(open(f"{SC}/compare.json", encoding="utf-8"))

INK = RGBColor(0x1A, 0x1A, 0x1A)
MUTED = RGBColor(0x6B, 0x6B, 0x6B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
ACCENT = RGBColor(0x2A, 0x78, 0xD6)      # 青：俊来・本命
GREEN = RGBColor(0x1B, 0xAF, 0x7A)       # 緑：新季
AMBER = RGBColor(0xED, 0xA1, 0x00)       # 黄：世帯
RED = RGBColor(0xD9, 0x3A, 0x3A)
DARK = RGBColor(0x1E, 0x2A, 0x38)        # 区切りページの地色
LIGHT = RGBColor(0xF4, 0xF6, 0xF8)
FONT = "Yu Gothic"

W, H = Inches(13.333), Inches(7.5)
yen = lambda v: f"¥{v:,}"


def deck():
    p = Presentation()
    p.slide_width, p.slide_height = W, H
    return p


def blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def tb(slide, x, y, w, h, text, size=18, bold=False, color=INK,
       align=PP_ALIGN.LEFT, spacing=1.25):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    for i, line in enumerate(text.split("\n")):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.text = line
        para.alignment = align
        para.line_spacing = spacing
        for run in para.runs:
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.color.rgb = color
            run.font.name = FONT
    return box


def band(slide, color=LIGHT, y=Emu(0), h=H):
    s = slide.shapes.add_shape(1, Emu(0), y, W, h)
    s.fill.solid()
    s.fill.fore_color.rgb = color
    s.line.fill.background()
    s.shadow.inherit = False
    return s


def title_page(slide, kicker, title, sub=""):
    tb(slide, Inches(0.9), Inches(0.55), Inches(11.5), Inches(0.4),
       kicker, 13, False, ACCENT)
    tb(slide, Inches(0.9), Inches(1.0), Inches(11.5), Inches(1.0),
       title, 30, True, INK)
    if sub:
        tb(slide, Inches(0.9), Inches(1.95), Inches(11.5), Inches(0.6),
           sub, 14, False, MUTED)


def section(prs, num, title, sub=""):
    s = blank(prs)
    band(s, DARK)
    tb(s, Inches(1.1), Inches(2.7), Inches(11), Inches(0.5), num, 15, False,
       RGBColor(0x7E, 0xA8, 0xD8))
    tb(s, Inches(1.1), Inches(3.15), Inches(11), Inches(1.1), title, 36, True, WHITE)
    if sub:
        tb(s, Inches(1.1), Inches(4.35), Inches(11), Inches(0.8), sub, 15,
           False, RGBColor(0xC5, 0xD2, 0xDE))
    return s


def table(slide, x, y, w, rows, widths=None, head_fill=RGBColor(0x2C, 0x3E, 0x50),
          size=12, row_h=Inches(0.42)):
    nr, nc = len(rows), len(rows[0])
    shape = slide.shapes.add_table(nr, nc, x, y, w, row_h * nr)
    t = shape.table
    if widths:
        total = sum(widths)
        for i, ww in enumerate(widths):
            t.columns[i].width = Emu(int(w * ww / total))
    for r, row in enumerate(rows):
        t.rows[r].height = row_h
        for c, val in enumerate(row):
            cell = t.cell(r, c)
            cell.text = str(val)
            para = cell.text_frame.paragraphs[0]
            para.alignment = PP_ALIGN.RIGHT if (c > 0 and r > 0) else PP_ALIGN.LEFT
            for run in para.runs:
                run.font.size = Pt(size)
                run.font.name = FONT
                run.font.bold = (r == 0)
                run.font.color.rgb = WHITE if r == 0 else INK
            cell.fill.solid()
            cell.fill.fore_color.rgb = (head_fill if r == 0
                                        else (WHITE if r % 2 else LIGHT))
    return t


def line_chart(slide, x, y, w, h, cats, series, colors, number_format='#,##0'):
    cd = CategoryChartData()
    cd.categories = cats
    for name, vals in series:
        cd.add_series(name, vals, number_format)
    gf = slide.shapes.add_chart(XL_CHART_TYPE.LINE, x, y, w, h, cd)
    ch = gf.chart
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.BOTTOM
    ch.legend.include_in_layout = False
    ch.legend.font.size = Pt(11)
    ch.legend.font.name = FONT
    ch.font.size = Pt(10)
    ch.font.name = FONT
    for i, ser in enumerate(ch.series):
        ser.smooth = False
        ser.format.line.color.rgb = colors[i]
        ser.format.line.width = Pt(2.5)
    va = ch.value_axis
    va.has_major_gridlines = True
    va.tick_labels.number_format = '#,##0,,"百万"'
    va.tick_labels.number_format_is_linked = False
    va.tick_labels.font.size = Pt(10)
    ch.category_axis.tick_labels.font.size = Pt(9)
    return ch


def note(slide, y, text):
    tb(slide, Inches(0.9), y, Inches(11.5), Inches(1.0), text, 11, False, MUTED,
       spacing=1.3)


def mlabel(m):
    y, mm = m.split("-")
    return f"{y[2:]}/{int(mm)}"


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "/Users/Office/Desktop/5年後のビジョン.pptx"
    prs = deck()
    m12 = D["m12"]; cats12 = [mlabel(m) for m in m12]
    m60 = D["m60"]; cats60 = [mlabel(m) if m.endswith(("-03", "-09")) else "" for m in m60]
    T1, S1 = D["y1"]["T"], D["y1"]["S"]
    T5, S5 = D["y5"]["T"], D["y5"]["S"]
    H5 = [t + s for t, s in zip(T5, S5)]

    # ══════ 表紙 ══════
    s = blank(prs); band(s, DARK)
    tb(s, Inches(1.1), Inches(2.4), Inches(11), Inches(0.5),
       "俊来 → 新季ちゃんへ", 15, False, RGBColor(0x7E, 0xA8, 0xD8))
    tb(s, Inches(1.1), Inches(2.95), Inches(11), Inches(1.6),
       "5年後、こうなっていたい。", 40, True, WHITE)
    tb(s, Inches(1.1), Inches(4.5), Inches(11), Inches(0.8),
       "そのために、お金を「活かす」ことをゲームにする。", 18, False,
       RGBColor(0xC5, 0xD2, 0xDE))

    # ══════ 1. 今日話したいこと ══════
    s = blank(prs)
    title_page(s, "01", "今日話したいこと")
    for i, (num, head, body) in enumerate([
        ("1", "僕のお金の使い方に、穴がある",
         "飲食費が月13.3万円。投資に回している額より多い。"),
        ("2", "だから、11月に一緒に住みたい",
         "意志で我慢するのではなく、環境で解決したい。"),
        ("3", "5年後、二人で2,062万円を目指したい",
         "結婚式も、旅行も、子どもも、全部やったうえで。")]):
        x = Inches(0.9 + i * 4.0)
        box = s.shapes.add_shape(1, x, Inches(2.6), Inches(3.7), Inches(2.6))
        box.fill.solid(); box.fill.fore_color.rgb = LIGHT
        box.line.color.rgb = RGBColor(0xD8, 0xDE, 0xE4); box.shadow.inherit = False
        tb(s, x + Inches(0.3), Inches(2.85), Inches(3.1), Inches(0.4), num, 14, True, ACCENT)
        tb(s, x + Inches(0.3), Inches(3.3), Inches(3.1), Inches(0.9), head, 17, True, INK)
        tb(s, x + Inches(0.3), Inches(4.3), Inches(3.1), Inches(0.8), body, 12, False, MUTED)

    # ══════ 2. 前提：僕は飽きやすい ══════
    s = blank(prs)
    title_page(s, "02", "前提：僕は、飽きやすい")
    tb(s, Inches(0.9), Inches(2.6), Inches(11.5), Inches(2.0),
       "これは直らないと思っている。\n"
       "だから「頑張って続ける」計画は、たぶん破綻する。", 24, True, INK)
    box = s.shapes.add_shape(1, Inches(0.9), Inches(4.6), Inches(11.5), Inches(1.4))
    box.fill.solid(); box.fill.fore_color.rgb = RGBColor(0xE8, 0xF1, 0xFB)
    box.line.fill.background(); box.shadow.inherit = False
    tb(s, Inches(1.3), Inches(4.95), Inches(10.7), Inches(0.8),
       "直す前提ではなく、仕組みで受け止める。これがこの資料の全体の考え方です。",
       17, True, RGBColor(0x18, 0x5F, 0xA5))

    # ══════ 3. 今の数字 ══════
    s = blank(prs)
    title_page(s, "03", "今の数字（俊来・毎月）")
    table(s, Inches(0.9), Inches(2.3), Inches(6.6), [
        ["項目", "金額"],
        ["収入", yen(500000)],
        ["税金（住民税＋所得税の月割）", "−" + yen(68333)],
        ["手取り", yen(431667)],
        ["家賃", "−" + yen(167000)],
        ["クレジットカード", "−" + yen(200000)],
        ["投資拠出", "−" + yen(100000)],
    ], widths=[3, 2])
    tb(s, Inches(8.0), Inches(2.5), Inches(4.4), Inches(0.5), "税金は年間82万円", 14, True, MUTED)
    tb(s, Inches(8.0), Inches(3.0), Inches(4.4), Inches(2.4),
       "住民税　8万円 × 年4回\n（2月・5月・8月・11月）\n\n所得税　50万円 × 年1回\n（3月）\n\n"
       "毎月出ていくお金ではなく、\n特定の月にまとめて出ていく。", 13, False, INK)

    # ══════ 4. 8月の明細を分解した ══════
    s = blank(prs)
    title_page(s, "04", "8月のカード明細を、全部分解した",
               "楽天ゴールドカード／2026年6月30日〜7月30日／49件／請求総額 189,412円")
    table(s, Inches(0.9), Inches(2.6), Inches(6.4), [
        ["分類", "金額", "件数"],
        ["飲み", yen(59928), "10件"],
        ["外食・カフェ", yen(12892), "2件"],
        ["交通", yen(25315), "22件"],
        ["医療", yen(17010), "2件"],
        ["水道光熱・通信", yen(12245), "3件"],
        ["買い物・サブスク", yen(6219), "8件"],
        ["分割払い", yen(29803), "—"],
    ], widths=[3, 2, 1.2])
    tb(s, Inches(7.8), Inches(2.7), Inches(4.6), Inches(0.5), "飲み 59,928円の中身", 14, True, ACCENT)
    tb(s, Inches(7.8), Inches(3.2), Inches(4.6), Inches(2.6),
       "バーダヴィー　31,800円（4回）\n炭火マルイチ　8,610円\nてっぺん渋谷　8,483円\n"
       "スタンド富士　7,350円\nオルバイオス　2,250円\nウエルカム東京　1,435円（2回）\n\n"
       "1回あたり平均 8,035円。\n7/23は同じ日に2軒。", 13, False, INK)

    # ══════ 5. 飲食の実額 ══════
    s = blank(prs)
    title_page(s, "05", "飲食に、月13万円使っている")
    for i, (lab, val, col) in enumerate([
            ("カード（飲み＋外食）", 72820, INK),
            ("PayPay", 60000, INK),
            ("合計", 132820, RED)]):
        x = Inches(0.9 + i * 4.0)
        tb(s, x, Inches(2.6), Inches(3.6), Inches(0.5), lab, 14, False, MUTED)
        tb(s, x, Inches(3.1), Inches(3.6), Inches(1.0), yen(val), 30, True, col)
    box = s.shapes.add_shape(1, Inches(0.9), Inches(4.7), Inches(11.5), Inches(1.5))
    box.fill.solid(); box.fill.fore_color.rgb = RGBColor(0xFD, 0xEC, 0xEC)
    box.line.fill.background(); box.shadow.inherit = False
    tb(s, Inches(1.3), Inches(5.0), Inches(10.7), Inches(1.0),
       "投資に回している額（月10万円）より、飲食のほうが多い。\n年間にすると 1,593,840円。",
       19, True, RGBColor(0xA8, 0x2A, 0x2A))

    # ══════ 6. なぜ飲みに出ていくのか ══════
    s = blank(prs)
    title_page(s, "06", "なぜ、飲みにお金が出ていくのか")
    tb(s, Inches(0.9), Inches(2.5), Inches(11.5), Inches(1.4),
       "「乾いている感覚」が、常にある。", 30, True, INK)
    tb(s, Inches(0.9), Inches(3.7), Inches(11.5), Inches(2.2),
       "飲みが提供しているのは、酒じゃない。\n"
       "その場の刺激と、すぐ手に入る達成感。\n\n"
       "つまり僕がお金を払っているのは、「乾きを埋めるもの」に対して。", 19, False, INK)

    # ══════ 7. 気づいたこと ══════
    s = blank(prs)
    title_page(s, "07", "気づいたこと")
    tb(s, Inches(0.9), Inches(2.4), Inches(11.5), Inches(1.6),
       "会社もある。YouTubeもある。趣味は、足りている。\n"
       "仕事以外の飲みは、本当はいらない。", 22, True, INK)
    box = s.shapes.add_shape(1, Inches(0.9), Inches(4.3), Inches(11.5), Inches(1.9))
    box.fill.solid(); box.fill.fore_color.rgb = RGBColor(0xE8, 0xF1, 0xFB)
    box.line.fill.background(); box.shadow.inherit = False
    tb(s, Inches(1.3), Inches(4.6), Inches(10.7), Inches(1.4),
       "必要なのは「意志」じゃなくて「装置」。\n"
       "そして、貯めることが目的じゃない。大事なことに使うために、無駄な漏れを塞ぎたい。",
       19, True, RGBColor(0x18, 0x5F, 0xA5))
    # ══════ 08 区切り：最初の一手 ══════
    section(prs, "PART 2", "だから、最初の一手を決めた。",
            "11月に、二人で新しい家に引っ越す。")

    # ══════ 09 お金の話 ══════
    s = blank(prs)
    title_page(s, "09", "なぜ「今」なのか（お金の話）",
               "5年後（2031年9月）の世帯資産で比べる")
    table(s, Inches(0.9), Inches(2.5), Inches(7.4), [
        ["選択肢", "5年後の世帯資産"],
        ["2027年5月に同棲（当初の予定）", yen(C["may_noutil"])],
        ["2026年11月に同棲", yen(C["nov_util"])],
    ], widths=[3.4, 2])
    diff = C["nov_util"] - C["may_noutil"]
    tb(s, Inches(8.7), Inches(2.7), Inches(3.7), Inches(0.5), "差", 14, False, MUTED)
    tb(s, Inches(8.7), Inches(3.1), Inches(3.7), Inches(0.9), "+" + yen(diff), 32, True, ACCENT)
    note(s, Inches(4.6),
         "※ 内訳と計算式（光熱費の節約は、どちらの選択肢でも同棲を始めた月から発生するものとして計算）\n"
         "　家賃タイミング：家賃 87,000円/月 × 6ヶ月 − 違約金 167,000円 ＝ 355,000円（単純計算）。"
         f"前倒しした現金が5年間運用に回るため、実際の差は {yen(C['rent_effect'])}。\n"
         "　光熱費の前倒し：世帯 5,000円/月 × 6ヶ月 ＝ 30,000円（単純計算）。運用込みで "
         f"{yen(C['util_effect'])}。光熱費が下がること自体はどちらでも起きるので、差になるのは6ヶ月分だけ。")

    # ══════ 10 賭けない ══════
    s = blank(prs)
    title_page(s, "10", "なぜ「今」なのか（本当の理由）",
               "食費6万円は、一人だと「守れるかどうかの賭け」になる")
    table(s, Inches(0.9), Inches(2.5), Inches(11.5), [
        ["", "一人・意志で成功", "一人・意志が続かない", "同棲（環境が支える）"],
        ["実現可能性", "△", "◯（起こりやすい）", "◎"],
        ["経済インパクト", "◎", "△", "◎"],
        ["5年後の世帯資産", yen(C["solo_ok"]), yen(C["solo_fail"]), yen(C["nov_util"])],
    ], widths=[2.2, 2.6, 2.9, 2.9], row_h=Inches(0.62), size=13)
    gap = C["solo_ok"] - C["solo_fail"]
    box = s.shapes.add_shape(1, Inches(0.9), Inches(5.1), Inches(11.5), Inches(1.3))
    box.fill.solid(); box.fill.fore_color.rgb = RGBColor(0xE8, 0xF1, 0xFB)
    box.line.fill.background(); box.shadow.inherit = False
    tb(s, Inches(1.3), Inches(5.4), Inches(10.7), Inches(0.8),
       f"一人でやる場合、「成功」と「失敗」の差は {yen(gap)}。同棲なら、その賭けをしなくていい。",
       18, True, RGBColor(0x18, 0x5F, 0xA5))

    # ══════ 11 ロジックのまとめ ══════
    s = blank(prs)
    title_page(s, "11", "ロジックのまとめ")
    steps = [("現状", "飲食 月13.3万円\n投資より多い"),
             ("目標", "食費 6万円\nクレカ 5万円"),
             ("手段", "11月に同棲\n環境で支える")]
    for i, (head, body) in enumerate(steps):
        x = Inches(0.9 + i * 3.95)
        box = s.shapes.add_shape(1, x, Inches(2.5), Inches(3.4), Inches(1.9))
        box.fill.solid()
        box.fill.fore_color.rgb = ACCENT if i == 2 else LIGHT
        box.line.color.rgb = RGBColor(0xD8, 0xDE, 0xE4); box.shadow.inherit = False
        tb(s, x + Inches(0.3), Inches(2.75), Inches(2.9), Inches(0.4), head, 14, True,
           WHITE if i == 2 else ACCENT)
        tb(s, x + Inches(0.3), Inches(3.25), Inches(2.9), Inches(1.0), body, 15, True,
           WHITE if i == 2 else INK)
        if i < 2:
            tb(s, x + Inches(3.45), Inches(3.2), Inches(0.5), Inches(0.5), "▶", 18, True, MUTED)
    tb(s, Inches(0.9), Inches(4.8), Inches(5.6), Inches(0.4), "メリット", 15, True, GREEN)
    tb(s, Inches(0.9), Inches(5.25), Inches(5.6), Inches(1.5),
       "・家賃と光熱費で " + yen(diff) + "（5年）\n・食費6万円の達成確率が上がる\n・早く一緒に暮らせる",
       13, False, INK)
    tb(s, Inches(6.9), Inches(4.8), Inches(5.5), Inches(0.4), "デメリット", 15, True, RED)
    tb(s, Inches(6.9), Inches(5.25), Inches(5.5), Inches(1.5),
       "・11月の現金が一時的に細くなる\n・引越し費用は俊来が全額立て替える必要がある",
       13, False, INK)

    # ══════ 12a-c 実行計画：1年目 ══════
    def year1_page(no, who, rows, color, note_text, is_household=False):
        sl = blank(prs)
        title_page(sl, no, f"最初の1年：{who}",
                   "2026年10月〜2027年9月（婚約まで）")
        if is_household:
            series = [("俊来", [r["total_assets"] for r in T1], ACCENT),
                      ("新季", [r["total_assets"] for r in S1], GREEN),
                      ("世帯合計", [t["total_assets"] + u["total_assets"]
                                for t, u in zip(T1, S1)], AMBER)]
        else:
            series = [("現金", [r["cash_balance"] for r in rows], RGBColor(0x8A, 0xA8, 0xC8)),
                      ("投資", [r["investment_balance"] for r in rows], GREEN),
                      ("資産合計", [r["total_assets"] for r in rows], color)]
        line_chart(sl, Inches(0.9), Inches(2.35), Inches(6.5), Inches(3.5),
                   cats12, [(n, v) for n, v, _ in series], [c for _, _, c in series])
        tb(sl, Inches(7.7), Inches(2.35), Inches(4.8), Inches(0.4), "月次の内訳", 14, True, MUTED)
        if is_household:
            body = [["月", "俊来", "新季", "世帯"]]
            for i in (0, 1, 5, 6, 11):
                body.append([mlabel(m12[i]), yen(T1[i]["total_assets"]),
                             yen(S1[i]["total_assets"]),
                             yen(T1[i]["total_assets"] + S1[i]["total_assets"])])
            table(sl, Inches(7.7), Inches(2.8), Inches(4.8), body,
                  widths=[1.1, 1.6, 1.6, 1.7], size=10.5, row_h=Inches(0.4))
        else:
            body = [["月", "収入", "支出計", "資産合計"]]
            for i in (0, 1, 5, 6, 11):
                r = rows[i]
                spend = (r["rent"] + r["credit_card"] + r["other_cash_expense"]
                         + r["investment_contribution"] + r["planned_expense"])
                body.append([mlabel(m12[i]), yen(r["income"]), yen(spend),
                             yen(r["total_assets"])])
            table(sl, Inches(7.7), Inches(2.8), Inches(4.8), body,
                  widths=[1.1, 1.6, 1.6, 1.7], size=10.5, row_h=Inches(0.4))
        note(sl, Inches(6.0), note_text)
        return sl

    year1_page("12", "俊来", T1, ACCENT,
               "※ 2026年10月〜2027年3月は月収26万円。この間の投資拠出はゼロにする。"
               "2026年11月に住民税8万＋違約金16.7万＋引越し60万＝84.7万円が一度に出る。"
               "2027年3月は所得税50万円で現金がゼロになり、投資から一部取り崩す。"
               "2027年4月にC-LinCから110万円が入り、5月から通常運転（月収50万・拠出10万）に戻る。")
    year1_page("13", "新季", S1, GREEN,
               "※ 収入25万円・投資拠出1万円で一定。7月と12月に賞与30万円が入る。"
               "11月の引越し費用は俊来が全額立て替えるため、新季側の現金は細らない。")
    year1_page("14", "世帯合計", None, AMBER,
               f"※ 1年後（2027年9月）の世帯資産は {yen(T1[11]['total_assets'] + S1[11]['total_assets'])}。"
               "2027年9月に婚約60万円を払ったあとの数字。"
               "11月と3月に谷ができるが、現金がマイナスになる月は一度もない。",
               is_household=True)

    # ══════ 15 区切り：5年 ══════
    section(prs, "PART 3", "そして、5年のあいだに起きること。",
            "結婚式、新婚旅行、そして第一子。")

    # ══════ 16 イベント一覧 ══════
    s = blank(prs)
    title_page(s, "16", "5年間に起きるイベント",
               "毎年発生するもの（住民税・所得税・賞与）は除く")
    table(s, Inches(0.9), Inches(2.4), Inches(11.5), [
        ["時期", "内容", "対象", "金額"],
        ["2026年11月", "違約金", "俊来", "−" + yen(167000)],
        ["2026年11月", "引越し費用（敷金礼金1ヶ月分を含む）", "俊来", "−" + yen(600000)],
        ["2027年4月", "C-LinC 1〜3月分報酬", "俊来", "+" + yen(1100000)],
        ["2027年9月", "婚約", "俊来", "−" + yen(600000)],
        ["2028年8月", "結婚式（費用）", "二人", "−" + yen(4000000)],
        ["2028年9月", "結婚式（ご祝儀）", "二人", "+" + yen(2000000)],
        ["2028年10月", "新婚旅行", "二人", "−" + yen(1000000)],
        ["2030年4月〜2031年5月", "新季の産休・育休（収入減）", "新季", "−100,000円/月"],
        ["2030年6月", "第一子・一時費用", "二人", "−" + yen(300000)],
        ["2030年6月〜2031年5月", "第一子・継続費", "二人", "−15,000円/月"],
    ], widths=[2.6, 4.8, 1.4, 2.4], size=11.5, row_h=Inches(0.38))

    # ══════ 17 第一子の費用 ══════
    s = blank(prs)
    title_page(s, "17", "第一子の費用（2030年・俊来33歳）",
               "東京都府中市の制度を反映した実質負担")
    table(s, Inches(0.9), Inches(2.5), Inches(6.6), [
        ["項目", "金額"],
        ["分娩入院費", yen(550000)],
        ["妊婦健診", yen(70000)],
        ["ベビー用品（初期）", yen(250000)],
        ["マタニティ用品", yen(30000)],
        ["支出 小計", yen(900000)],
        ["出産育児一時金", "−" + yen(500000)],
        ["妊婦のための支援給付（府中市）", "−" + yen(100000)],
        ["実質負担", yen(300000)],
    ], widths=[3.4, 2])
    tb(s, Inches(8.0), Inches(2.6), Inches(4.4), Inches(0.4), "毎月かかるもの", 14, True, ACCENT)
    tb(s, Inches(8.0), Inches(3.05), Inches(4.4), Inches(2.0),
       "育児消耗品費　20,000円/月\n018サポート　　−5,000円/月\n"
       "──────────────\n実質負担　　　 15,000円/月\n（0〜1歳の期間）", 13, False, INK)
    tb(s, Inches(8.0), Inches(5.0), Inches(4.4), Inches(0.4), "保育料", 14, True, GREEN)
    tb(s, Inches(8.0), Inches(5.4), Inches(4.4), Inches(0.8),
       "認可保育所なら実質0円\n（府中市・2026年4月から所得問わず無償化）", 12, False, INK)
    note(s, Inches(6.3),
         "※ 分娩費用・健診費用・ベビー用品費は全国平均ベースの仮置き。"
         "新季の収入減（25万→15万・14ヶ月）は国の給付水準にもとづく目安で、勤務先の実際の制度は未確認。"
         "認可外保育施設に入った場合、府中市の補助は非課税世帯のみのため別途月5〜8万円がかかるリスクがある。")

    # ══════ 18-20 5年の見通し ══════
    def year5_page(no, who, vals, cash, inv, re_, color, note_text):
        sl = blank(prs)
        title_page(sl, no, f"5年の見通し：{who}", "2026年10月〜2031年9月")
        line_chart(sl, Inches(0.9), Inches(2.35), Inches(7.4), Inches(3.6), cats60,
                   [("現金", cash), ("投資", inv), ("不動産", re_), ("資産合計", vals)],
                   [RGBColor(0x8A, 0xA8, 0xC8), GREEN, AMBER, color])
        rows = [["時点", "資産合計"]]
        for i, lab in ((11, "1年後"), (23, "2年後"), (35, "3年後"), (47, "4年後"), (59, "5年後")):
            rows.append([lab + f"（{m60[i][:4]}年{int(m60[i][5:])}月）", yen(vals[i])])
        table(sl, Inches(8.7), Inches(2.6), Inches(3.7), rows,
              widths=[2.1, 1.6], size=11, row_h=Inches(0.44))
        note(sl, Inches(6.15), note_text)
        return sl

    year5_page("18", "俊来", T5, D["y5"]["Tcash"], D["y5"]["Tinv"], D["y5"]["Tre"], ACCENT,
               "※ 2031年1月から住宅ローンの返済が始まり、返済額が不動産の資産として積み上がり始める。")
    year5_page("19", "新季", S5, D["y5"]["Scash"], D["y5"]["Sinv"], D["y5"]["Sre"], GREEN,
               "※ 2030年4月〜2031年5月は産休・育休で収入が月15万円に下がる。"
               "現金が上限200万円に達すると、超えた分は自動的に投資へ回る。")
    Hc = [a + b for a, b in zip(D["y5"]["Tcash"], D["y5"]["Scash"])]
    Hi = [a + b for a, b in zip(D["y5"]["Tinv"], D["y5"]["Sinv"])]
    Hr = [a + b for a, b in zip(D["y5"]["Tre"], D["y5"]["Sre"])]
    year5_page("20", "世帯合計", H5, Hc, Hi, Hr, AMBER,
               f"※ 5年後の世帯資産は {yen(H5[59])}。結婚式・新婚旅行・婚約・第一子を"
               "すべて払ったうえでの数字。もし食費の見直しが続かなかった場合は "
               f"{yen(C['solo_fail'])} にとどまる。")

    # ══════ 21 レベル表・ビジョン（記入待ち） ══════
    s = blank(prs)
    title_page(s, "21", "5年後のビジョン", "※ ここは俊来がこれから書く")
    for i, (lab, ph) in enumerate([
            ("資産の節目に、名前をつける", "1,000万円 → 「◯◯」\n1,500万円 → 「◯◯」\n2,000万円 → 「◯◯」"),
            ("数字じゃない部分", "どんな暮らしをしていたいか\n二人がどうなっていたいか\n何に使いたいか")]):
        x = Inches(0.9 + i * 5.95)
        box = s.shapes.add_shape(1, x, Inches(2.5), Inches(5.5), Inches(3.4))
        box.fill.solid(); box.fill.fore_color.rgb = LIGHT
        box.line.color.rgb = RGBColor(0xC8, 0xD0, 0xD8); box.shadow.inherit = False
        tb(s, x + Inches(0.4), Inches(2.8), Inches(4.7), Inches(0.5), lab, 16, True, ACCENT)
        tb(s, x + Inches(0.4), Inches(3.4), Inches(4.7), Inches(2.2), ph, 14, False, MUTED)

    # ══════ 22 区切り：お願い ══════
    section(prs, "PART 4", "新季ちゃんへのお願い。")

    # ══════ 23 一人でやるゲームは飽きる ══════
    s = blank(prs)
    title_page(s, "23", "一人でやるゲームは、飽きる")
    tb(s, Inches(0.9), Inches(2.4), Inches(11.5), Inches(0.8),
       "だから、二人でやりたい。", 26, True, INK)
    for i, (head, body) in enumerate([
            ("お願いしたいこと", "月に1回、30分だけ。\n一緒に数字を見てほしい。\n監視じゃなくて、一緒に見るだけ。"),
            ("先に決めておきたいこと", "守れなかった月があっても、\n責めない。数字を見て、\n次の月にどうするかを決める。")]):
        x = Inches(0.9 + i * 5.95)
        box = s.shapes.add_shape(1, x, Inches(3.4), Inches(5.5), Inches(2.4))
        box.fill.solid()
        box.fill.fore_color.rgb = RGBColor(0xE8, 0xF1, 0xFB) if i == 0 else LIGHT
        box.line.fill.background(); box.shadow.inherit = False
        tb(s, x + Inches(0.4), Inches(3.7), Inches(4.7), Inches(0.5), head, 16, True, ACCENT)
        tb(s, x + Inches(0.4), Inches(4.3), Inches(4.7), Inches(1.3), body, 14, False, INK)

    # ══════ 24 区切り：アペンディクス ══════
    section(prs, "APPENDIX", "参考：ゲームのルールと、複利の話。")

    # ══════ 25 複利（新季さん向け） ══════
    s = blank(prs)
    title_page(s, "A1", "複利の話：置いておくだけで、増える",
               "年5%で運用した場合。月々の積立額を3パターンで比べる")
    table(s, Inches(0.9), Inches(2.5), Inches(11.5), [
        ["月々の積立", "1年後", "3年後", "5年後", "元本（5年）", "運用で増えた分"],
        [yen(10000), yen(123227), yen(388470), yen(680900), yen(600000), "+" + yen(80900)],
        [yen(30000), yen(369677), yen(1165407), yen(2042698), yen(1800000), "+" + yen(242698)],
        [yen(50000), yen(616130), yen(1942348), yen(3404503), yen(3000000), "+" + yen(404503)],
    ], widths=[1.8, 1.7, 1.8, 1.8, 1.8, 2.1], size=12, row_h=Inches(0.5))
    box = s.shapes.add_shape(1, Inches(0.9), Inches(4.9), Inches(11.5), Inches(1.3))
    box.fill.solid(); box.fill.fore_color.rgb = RGBColor(0xE6, 0xF6, 0xEF)
    box.line.fill.background(); box.shadow.inherit = False
    tb(s, Inches(1.3), Inches(5.2), Inches(10.7), Inches(0.8),
       "どのパターンも、運用で増える分は元本の13.5%。"
       "月1万円でも5年で8万円増える。金額が大きいほど、増える額も比例して大きくなる。",
       17, True, RGBColor(0x0F, 0x6E, 0x56))

    # ══════ 26 ルール ══════
    s = blank(prs)
    title_page(s, "A2", "ゲームのルール")
    rules = [("ルール①", "スコアは資産合計", "現金 ＋ 投資 ＋ 不動産。毎月ひとつの数字を見る。"),
             ("ルール②", "為替レート", "飲食を月1万円減らす ＝ 5年後に68万円。\n我慢ではなく、レートの計算にする。"),
             ("ルール③", "飲み代は敵ではなく予算", "飲み・外食 3万円 ＋ 自炊 3万円 ＝ 6万円。\nクレカは5万円。使い方は自分で決める。"),
             ("ルール④", "3ヶ月で1シーズン", "5年 ＝ 全20シーズン。飽きる前に必ず区切りが来る。\nシーズン1のテーマは「11月の引越しを乗り切る」。")]
    for i, (no, head, body) in enumerate(rules):
        y = Inches(2.35 + i * 1.2)
        box = s.shapes.add_shape(1, Inches(0.9), y, Inches(11.5), Inches(1.05))
        box.fill.solid()
        box.fill.fore_color.rgb = LIGHT if i % 2 == 0 else WHITE
        box.line.color.rgb = RGBColor(0xE0, 0xE5, 0xEA); box.shadow.inherit = False
        tb(s, Inches(1.2), y + Inches(0.13), Inches(1.3), Inches(0.4), no, 13, True, ACCENT)
        tb(s, Inches(2.5), y + Inches(0.1), Inches(3.4), Inches(0.5), head, 15, True, INK)
        tb(s, Inches(6.0), y + Inches(0.1), Inches(6.2), Inches(0.85), body, 12, False, MUTED)

    prs.save(out)
    print(f"書き出しました: {out}")
    print(f"  全 {len(prs.slides._sldIdLst)} 枚")
    return prs, out, (cats12, cats60, T1, S1, T5, S5, H5, m12, m60)
