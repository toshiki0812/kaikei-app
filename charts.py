"""Plotlyグラフ生成。

配色は検証済みカテゴリカルパレットを固定順で使用（サーフェス #fcfcfb に対して
全チェックPASS・最小隣接CVD ΔE 24.2）。金額はすべて同一軸・同一単位（万円）で扱い、
2軸グラフは使わない。実績は実線、想定（将来予測）は破線で描き分ける。
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from theme import (AQUA, AXIS, BLUE, GREEN, GRID, INK, INK_2, MUTED, RED,
                   SURFACE, VIOLET, YELLOW, FONT_STACK)

MAN = 10_000  # 万円換算


def _dates(df) -> list:
    return pd.to_datetime(df["month"] + "-01").tolist()


def _split(statuses: list[str], values: list[float]):
    """実績区間と予測区間の2系列に分ける（境界は両方に値を入れて線を繋ぐ）。"""
    n = len(values)
    first_projected = next((i for i, s in enumerate(statuses) if s == "projected"), None)
    if first_projected is None:
        return list(values), [None] * n
    actual = [values[i] if i < first_projected else None for i in range(n)]
    projected = [None] * n
    for i in range(max(first_projected - 1, 0), n):
        projected[i] = values[i]
    return actual, projected


def _base(fig: go.Figure, title: str, height: int = 360, y_title: str = "万円"):
    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", font=dict(size=15.5, color=INK),
                   x=0, xanchor="left", y=0.97, yanchor="top"),
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font=dict(family=FONT_STACK, size=12, color=INK_2),
        height=height,
        margin=dict(l=8, r=20, t=88, b=14),
        hoverlabel=dict(bgcolor="#ffffff", bordercolor=AXIS, align="left",
                        font=dict(family=FONT_STACK, color=INK, size=12.5)),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0,
                    font=dict(size=11.5, color=INK_2), itemsizing="constant",
                    bgcolor="rgba(0,0,0,0)"),
    )
    # 軸・グリッドはすべて実線のヘアライン（破線は「予測」の意味に予約）
    fig.update_xaxes(showgrid=False, showline=True, linecolor=AXIS, linewidth=1,
                     ticks="outside", tickcolor=AXIS, ticklen=4,
                     tickfont=dict(color=MUTED, size=11))
    fig.update_yaxes(showgrid=True, gridcolor=GRID, gridwidth=1, griddash="solid",
                     zeroline=False, showline=False, tickformat=",",
                     tickfont=dict(color=MUTED, size=11),
                     title=dict(text=y_title, font=dict(color=MUTED, size=11)))
    return fig


def _endpoint_label(fig: go.Figure, x, y_man: float, raw: float, color: str):
    """終端だけを直接ラベルする（全点への数値表示はしない）。"""
    fig.add_trace(go.Scatter(
        x=[x], y=[y_man], mode="markers", marker=dict(size=9, color=color,
                                                       line=dict(width=2, color=SURFACE)),
        showlegend=False, hoverinfo="skip",
    ))
    fig.add_annotation(x=x, y=y_man, text=f"<b>¥{raw:,.0f}</b>", showarrow=False,
                       xanchor="right", yanchor="bottom", yshift=12,
                       font=dict(size=12, color=color, family=FONT_STACK))


def _balance_chart(df, value_col: str, title: str, color: str,
                   actual_name: str, projected_name: str) -> go.Figure:
    x = _dates(df)
    raw = df[value_col].tolist()
    values = [v / MAN for v in raw]
    actual, projected = _split(df["data_status"].tolist(), values)

    fig = go.Figure()
    for ys, name, dash in ((actual, actual_name, "solid"), (projected, projected_name, "dash")):
        fig.add_trace(go.Scatter(
            x=x, y=ys, mode="lines", name=name,
            line=dict(color=color, width=2, dash=dash),
            customdata=raw,
            hovertemplate="%{fullData.name}　<b>¥%{customdata:,.0f}</b><extra></extra>",
        ))
    _endpoint_label(fig, x[-1], values[-1], raw[-1], color)
    _base(fig, title)
    fig.update_xaxes(showspikes=True, spikemode="across", spikethickness=1,
                     spikecolor=AXIS, spikedash="solid", dtick="M12", tickformat="%Y年")
    fig.update_layout(hovermode="x unified")
    return fig


def cash_balance_chart(df) -> go.Figure:
    return _balance_chart(df, "cash_balance", "現金残高の推移", BLUE,
                          "現金残高（実績）", "現金残高（想定）")


def investment_chart(df, expected_return_pct: float) -> go.Figure:
    return _balance_chart(df, "investment_balance", "投資残高の推移", VIOLET,
                          "投資残高（実績）", f"投資残高（想定利回り{expected_return_pct:g}%）")


# プラン比較用。検証済みスロットを固定順で割り当てる（巡回・生成はしない）
PLAN_COLORS = [BLUE, AQUA, YELLOW, GREEN, VIOLET, RED]
MAX_COMPARED_PLANS = len(PLAN_COLORS)


def plan_comparison_chart(frames: dict, value_col: str, title: str) -> go.Figure:
    """複数プランの残高推移を1枚に重ねる。全プラン同じ軸・同じ単位（万円）。

    frames: {プラン名: build_projection の DataFrame}
    """
    fig = go.Figure()
    for i, (plan_name, pdf) in enumerate(frames.items()):
        raw = pdf[value_col].tolist()
        fig.add_trace(go.Scatter(
            x=_dates(pdf), y=[v / MAN for v in raw], mode="lines", name=plan_name,
            line=dict(color=PLAN_COLORS[i % len(PLAN_COLORS)], width=2),
            customdata=raw,
            hovertemplate="%{fullData.name}　<b>¥%{customdata:,.0f}</b><extra></extra>",
        ))
    _base(fig, title)
    fig.update_xaxes(showspikes=True, spikemode="across", spikethickness=1,
                     spikecolor=AXIS, spikedash="solid", dtick="M12", tickformat="%Y年")
    fig.update_layout(hovermode="x unified")
    return fig


def expense_breakdown_chart(df, people: list[dict], n_months: int = 12) -> go.Figure:
    """月々の支出内訳（積み上げ）と収入（基準線）。単位はすべて万円・同一軸。"""
    sub = df.head(n_months)
    x = _dates(sub)

    # カテゴリは固定順のスロットに割り当てる（人数が増えても巡回させない）
    segments = [("rent", "家賃", BLUE)]
    cc_colors = [AQUA, YELLOW]
    for i, p in enumerate(people[:2]):
        segments.append((f"credit_card_p{p['id']}", f"{p['name']}のクレカ", cc_colors[i]))
    segments += [
        ("_investment_total", "投資（自動振替含む）", GREEN),
        ("other_cash_expense", "その他（現金）", VIOLET),
        ("_other_combined", "その他・臨時", RED),
    ]

    sub = sub.copy()
    # 自動振替は現金から投資へ移すだけだが、現金の出入りとしては拠出と同じ扱い
    sub["_investment_total"] = sub["investment_contribution"] + sub["cash_sweep"]
    sub["_other_combined"] = sub["other_expense"] + sub["planned_expense"]

    fig = go.Figure()
    for col, label, color in segments:
        raw = sub[col].tolist()
        fig.add_trace(go.Bar(
            x=x, y=[v / MAN for v in raw], name=label,
            marker=dict(color=color, line=dict(color=SURFACE, width=1.5)),
            customdata=raw,
            hovertemplate="%{fullData.name}　¥%{customdata:,.0f}<extra></extra>",
        ))

    income_raw = sub["income_total"].tolist()
    fig.add_trace(go.Scatter(
        x=x, y=[v / MAN for v in income_raw], mode="lines", name="収入合計",
        line=dict(color=INK_2, width=2),
        customdata=income_raw,
        hovertemplate="収入合計　<b>¥%{customdata:,.0f}</b><extra></extra>",
    ))

    _base(fig, f"月々の支出内訳と収入（直近{n_months}ヶ月）", height=400)
    # 積み上げの角を丸めて、カードの丸みと揃える
    fig.update_layout(barmode="stack", bargap=0.42, barcornerradius=5,
                      hovermode="x unified")
    fig.update_xaxes(dtick="M1", tickformat="%y年%-m月")
    return fig
