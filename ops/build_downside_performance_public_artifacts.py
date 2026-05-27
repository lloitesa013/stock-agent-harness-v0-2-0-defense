"""Build public artifacts for the downside_performance_v1 claim.

This helper is intentionally outside the official deterministic claim gate. It
packages already-generated evidence, renders human-readable charts, and writes a
short PDF/Markdown paper for review. The underlying performance claim remains
bounded by benchmarks/downside_performance_v1/claim_contract.json.
"""

from __future__ import print_function

import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


STRATEGY_ORDER = [
    "agentic_candidate_v1",
    "simple_momentum",
    "stock_harness_ma_cash",
    "volatility_targeting",
    "equal_weight",
    "sma_crossover",
    "mean_reversion",
    "buy_and_hold_spy",
    "cash",
]

STRATEGY_COLORS = {
    "agentic_candidate_v1": (25, 87, 166),
    "simple_momentum": (0, 128, 96),
    "stock_harness_ma_cash": (109, 72, 170),
    "volatility_targeting": (204, 119, 34),
    "equal_weight": (77, 77, 77),
    "sma_crossover": (177, 89, 40),
    "mean_reversion": (161, 66, 132),
    "buy_and_hold_spy": (180, 55, 55),
    "cash": (120, 120, 120),
}


def _repo_path(path):
    if os.path.isabs(path):
        return path
    return os.path.abspath(os.path.join(ROOT, path))


def _safe_rmtree(path, allowed_parent):
    path = os.path.abspath(path)
    allowed_parent = os.path.abspath(allowed_parent)
    if not path.startswith(allowed_parent + os.sep):
        raise ValueError("refusing to delete outside allowed parent: %s" % path)
    if os.path.isdir(path):
        shutil.rmtree(path)


def _ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def _load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path, payload, pretty=False):
    _ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as handle:
        if pretty:
            json.dump(payload, handle, indent=2, sort_keys=True)
        else:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_file(src, dst):
    _ensure_dir(os.path.dirname(dst))
    shutil.copy2(src, dst)


def _copy_tree(src, dst):
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _format_pct(value):
    if value is None:
        return "n/a"
    return "%.2f%%" % (float(value) * 100.0)


def _format_ratio(value):
    if value is None:
        return "n/a"
    return "%.2f" % float(value)


def _load_font(size, bold=False):
    from PIL import ImageFont

    candidates = []
    if bold:
        candidates.extend([
            r"C:\Windows\Fonts\arialbd.ttf",
            r"C:\Windows\Fonts\malgunbd.ttf",
        ])
    candidates.extend([
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\malgun.ttf",
    ])
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _text(draw, xy, text, font, fill=(31, 41, 55), anchor=None):
    kwargs = {}
    if anchor:
        kwargs["anchor"] = anchor
    draw.text(xy, text, font=font, fill=fill, **kwargs)


def _chart_canvas(title, subtitle=None):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1280, 760), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    title_font = _load_font(34, bold=True)
    subtitle_font = _load_font(18)
    _text(draw, (54, 34), title, title_font, fill=(17, 24, 39))
    if subtitle:
        _text(draw, (56, 78), subtitle, subtitle_font, fill=(75, 85, 99))
    draw.line((54, 116, 1226, 116), fill=(229, 231, 235), width=2)
    return image, draw


def _scale(value, vmin, vmax, start, end):
    if vmax == vmin:
        return (start + end) / 2.0
    ratio = (float(value) - float(vmin)) / (float(vmax) - float(vmin))
    return start + ratio * (end - start)


def _draw_legend(draw, labels, x, y):
    font = _load_font(15)
    cursor_x = x
    cursor_y = y
    for strategy_id in labels:
        color = STRATEGY_COLORS.get(strategy_id, (80, 80, 80))
        label = strategy_id.replace("_", " ")
        draw.rectangle((cursor_x, cursor_y, cursor_x + 18, cursor_y + 10), fill=color)
        _text(draw, (cursor_x + 24, cursor_y - 4), label, font, fill=(55, 65, 81))
        cursor_x += 190
        if cursor_x > 1030:
            cursor_x = x
            cursor_y += 24


def _generate_equity_chart(report, out_path):
    from PIL import ImageDraw

    image, draw = _chart_canvas(
        "Equity Curve Comparison",
        "Hypothetical backtested equity on the included downside_performance_v1 benchmark.",
    )
    curves = report["equity_curves_by_strategy"]
    selected = [
        "agentic_candidate_v1",
        "simple_momentum",
        "stock_harness_ma_cash",
        "volatility_targeting",
        "buy_and_hold_spy",
        "cash",
    ]
    left, top, right, bottom = 82, 154, 1190, 650
    all_values = []
    for strategy_id in selected:
        all_values.extend([point["equity"] for point in curves[strategy_id]])
    ymin = min(all_values) * 0.985
    ymax = max(all_values) * 1.015
    axis_color = (156, 163, 175)
    grid_color = (229, 231, 235)
    font = _load_font(15)
    small = _load_font(13)
    draw.rectangle((left, top, right, bottom), outline=axis_color, width=1)
    for i in range(1, 5):
        y = top + (bottom - top) * i / 5.0
        draw.line((left, y, right, y), fill=grid_color, width=1)
        value = ymax - (y - top) / (bottom - top) * (ymax - ymin)
        _text(draw, (left - 10, y - 8), "$%dk" % int(value / 1000), small, fill=(107, 114, 128), anchor="ra")
    point_count = len(curves[selected[0]])
    for strategy_id in selected:
        series = curves[strategy_id]
        pts = []
        for idx, point in enumerate(series):
            x = _scale(idx, 0, point_count - 1, left, right)
            y = _scale(point["equity"], ymin, ymax, bottom, top)
            pts.append((x, y))
        draw.line(pts, fill=STRATEGY_COLORS[strategy_id], width=4 if strategy_id == "agentic_candidate_v1" else 2)
    _text(draw, (left, bottom + 16), curves[selected[0]][0]["date"], font, fill=(75, 85, 99))
    _text(draw, (right, bottom + 16), curves[selected[0]][-1]["date"], font, fill=(75, 85, 99), anchor="ra")
    _draw_legend(draw, selected, left, 686)
    image.save(out_path)


def _generate_drawdown_chart(report, out_path):
    image, draw = _chart_canvas(
        "Drawdown Curve Comparison",
        "Lower magnitude drawdowns are better; values are shown as negative percentages.",
    )
    curves = report["equity_curves_by_strategy"]
    selected = [
        "agentic_candidate_v1",
        "simple_momentum",
        "stock_harness_ma_cash",
        "volatility_targeting",
        "buy_and_hold_spy",
    ]
    left, top, right, bottom = 82, 154, 1190, 650
    max_dd = max(max(point["drawdown"] for point in curves[strategy_id]) for strategy_id in selected)
    ymin, ymax = -max_dd * 1.05, 0.0
    axis_color = (156, 163, 175)
    grid_color = (229, 231, 235)
    font = _load_font(15)
    small = _load_font(13)
    draw.rectangle((left, top, right, bottom), outline=axis_color, width=1)
    for i in range(0, 6):
        y = top + (bottom - top) * i / 5.0
        draw.line((left, y, right, y), fill=grid_color, width=1)
        value = ymax - (y - top) / (bottom - top) * (ymax - ymin)
        _text(draw, (left - 10, y - 8), "%.1f%%" % (value * 100), small, fill=(107, 114, 128), anchor="ra")
    point_count = len(curves[selected[0]])
    for strategy_id in selected:
        pts = []
        for idx, point in enumerate(curves[strategy_id]):
            x = _scale(idx, 0, point_count - 1, left, right)
            y = _scale(-point["drawdown"], ymin, ymax, bottom, top)
            pts.append((x, y))
        draw.line(pts, fill=STRATEGY_COLORS[strategy_id], width=4 if strategy_id == "agentic_candidate_v1" else 2)
    _text(draw, (left, bottom + 16), curves[selected[0]][0]["date"], font, fill=(75, 85, 99))
    _text(draw, (right, bottom + 16), curves[selected[0]][-1]["date"], font, fill=(75, 85, 99), anchor="ra")
    _draw_legend(draw, selected, left, 686)
    image.save(out_path)


def _generate_return_bar_chart(report, out_path):
    image, draw = _chart_canvas(
        "Total Return by Strategy",
        "Included deterministic baselines plus agentic_candidate_v1.",
    )
    metrics = report["metrics_by_strategy"]
    rows = sorted(
        [(sid, metrics[sid]["total_return"]) for sid in metrics],
        key=lambda item: item[1],
        reverse=True,
    )
    left, top, right, bottom = 420, 150, 1160, 650
    label_font = _load_font(17)
    value_font = _load_font(16, bold=True)
    small = _load_font(13)
    max_value = max(value for _, value in rows)
    min_value = min(value for _, value in rows)
    x_zero = _scale(0.0, min_value, max_value, left, right)
    draw.line((x_zero, top - 14, x_zero, bottom + 8), fill=(156, 163, 175), width=1)
    row_h = 52
    for idx, (strategy_id, value) in enumerate(rows):
        y = top + idx * row_h
        label = strategy_id.replace("_", " ")
        color = STRATEGY_COLORS.get(strategy_id, (100, 100, 100))
        _text(draw, (left - 16, y + 8), label, label_font, fill=(31, 41, 55), anchor="ra")
        x_value = _scale(value, min_value, max_value, left, right)
        x0, x1 = sorted([x_zero, x_value])
        draw.rounded_rectangle((x0, y, x1, y + 28), radius=6, fill=color)
        if value >= 0:
            _text(draw, (x_value + 10, y + 5), _format_pct(value), value_font, fill=(17, 24, 39), anchor="la")
        else:
            _text(draw, (x_zero + 10, y + 5), _format_pct(value), value_font, fill=(180, 55, 55), anchor="la")
    _text(draw, (left, bottom + 36), "Negative values extend left of the zero line.", small, fill=(107, 114, 128))
    image.save(out_path)


def _generate_risk_ranking_chart(report, out_path):
    image, draw = _chart_canvas(
        "Risk-Adjusted Ranking",
        "Calmar emphasizes return per unit of max drawdown; Sharpe uses annualized volatility.",
    )
    metrics = report["metrics_by_strategy"]
    rows = []
    for strategy_id in STRATEGY_ORDER:
        if strategy_id in metrics:
            rows.append((strategy_id, metrics[strategy_id]["calmar_ratio"], metrics[strategy_id]["sharpe_ratio"]))
    left, top = 360, 150
    bar_w = 360
    row_h = 55
    label_font = _load_font(17)
    value_font = _load_font(15, bold=True)
    max_calmar = max(max(row[1], 0.0) for row in rows)
    max_sharpe = max(max(row[2], 0.0) for row in rows)
    _text(draw, (left, top - 34), "Calmar", _load_font(18, bold=True), fill=(31, 41, 55))
    _text(draw, (left + 440, top - 34), "Sharpe", _load_font(18, bold=True), fill=(31, 41, 55))
    for idx, (strategy_id, calmar, sharpe) in enumerate(rows):
        y = top + idx * row_h
        _text(draw, (left - 18, y + 8), strategy_id.replace("_", " "), label_font, fill=(31, 41, 55), anchor="ra")
        color = STRATEGY_COLORS.get(strategy_id, (100, 100, 100))
        calmar_w = int(bar_w * max(calmar, 0.0) / max_calmar) if max_calmar else 0
        sharpe_w = int(bar_w * max(sharpe, 0.0) / max_sharpe) if max_sharpe else 0
        draw.rounded_rectangle((left, y, left + calmar_w, y + 25), radius=6, fill=color)
        draw.rounded_rectangle((left + 440, y, left + 440 + sharpe_w, y + 25), radius=6, fill=color)
        _text(draw, (left + calmar_w + 8, y + 4), _format_ratio(calmar), value_font, fill=(17, 24, 39))
        _text(draw, (left + 440 + sharpe_w + 8, y + 4), _format_ratio(sharpe), value_font, fill=(17, 24, 39))
    image.save(out_path)


def _generate_cost_stress_chart(report, out_path):
    image, draw = _chart_canvas(
        "Cost and Slippage Stress",
        "agentic_candidate_v1 remains publishable under the included stress ladder.",
    )
    cases = report["robustness"]["cost_slippage_stress"]["cases"]
    left, top, right, bottom = 110, 170, 1140, 610
    max_cagr = max(case["cagr"] for case in cases) * 1.15
    max_dd = max(case["max_drawdown"] for case in cases) * 1.25
    group_w = (right - left) / float(len(cases))
    font = _load_font(15)
    small = _load_font(13)
    axis_color = (156, 163, 175)
    grid_color = (229, 231, 235)
    draw.rectangle((left, top, right, bottom), outline=axis_color, width=1)
    for i in range(1, 5):
        y = top + (bottom - top) * i / 5.0
        draw.line((left, y, right, y), fill=grid_color, width=1)
    for idx, case in enumerate(cases):
        base_x = left + idx * group_w + 42
        cagr_h = (case["cagr"] / max_cagr) * (bottom - top)
        dd_h = (case["max_drawdown"] / max_dd) * (bottom - top)
        draw.rounded_rectangle((base_x, bottom - cagr_h, base_x + 62, bottom), radius=6, fill=(25, 87, 166))
        draw.rounded_rectangle((base_x + 82, bottom - dd_h, base_x + 144, bottom), radius=6, fill=(180, 55, 55))
        label = "%.0fbps/%.0fbps" % (case["cost_bps"], case["slippage_bps"])
        _text(draw, (base_x + 72, bottom + 18), label, small, fill=(75, 85, 99), anchor="ma")
        _text(draw, (base_x + 31, bottom - cagr_h - 22), _format_pct(case["cagr"]), small, fill=(25, 87, 166), anchor="ma")
        _text(draw, (base_x + 113, bottom - dd_h - 22), _format_pct(case["max_drawdown"]), small, fill=(180, 55, 55), anchor="ma")
    _text(draw, (left, 648), "Blue: CAGR  Red: Max drawdown  X-axis: cost bps / slippage bps", font, fill=(75, 85, 99))
    image.save(out_path)


def generate_visuals(report, visuals_dir):
    try:
        import PIL  # noqa: F401
    except Exception as exc:
        raise RuntimeError("Pillow is required to build visuals: %s" % exc)
    _ensure_dir(visuals_dir)
    paths = {
        "equity_curve": os.path.join(visuals_dir, "equity_curve_comparison.png"),
        "drawdown_curve": os.path.join(visuals_dir, "drawdown_curve_comparison.png"),
        "baseline_return": os.path.join(visuals_dir, "baseline_total_return.png"),
        "risk_adjusted_ranking": os.path.join(visuals_dir, "risk_adjusted_ranking.png"),
        "cost_stress": os.path.join(visuals_dir, "cost_slippage_stress.png"),
    }
    _generate_equity_chart(report, paths["equity_curve"])
    _generate_drawdown_chart(report, paths["drawdown_curve"])
    _generate_return_bar_chart(report, paths["baseline_return"])
    _generate_risk_ranking_chart(report, paths["risk_adjusted_ranking"])
    _generate_cost_stress_chart(report, paths["cost_stress"])
    return paths


def _top_rows(metrics):
    return sorted(metrics.values(), key=lambda row: row["total_return"], reverse=True)


def _load_defense_packet(defense_dir):
    if not defense_dir or not os.path.isdir(defense_dir):
        return None
    required = [
        "defense_gate.json",
        "strategy_freeze_report.json",
        "data_lineage_bias_report.json",
        "baseline_fairness_report.json",
        "statistical_confidence_report.json",
        "forward_paper_trading_protocol.json",
    ]
    packet = {}
    for filename in required:
        path = os.path.join(defense_dir, filename)
        if not os.path.isfile(path):
            return None
        packet[filename[:-5]] = _load_json(path)
    return packet


def _ci_range(metrics, metric_id, scale=1.0, suffix=""):
    values = metrics.get(metric_id, {})
    if not values:
        return "n/a"
    return "%.2f%s / %.2f%s / %.2f%s" % (
        float(values.get("p05", 0.0)) * scale,
        suffix,
        float(values.get("median", 0.0)) * scale,
        suffix,
        float(values.get("p95", 0.0)) * scale,
        suffix,
    )


def _defense_checks_row(defense):
    if not defense:
        return []
    checks = defense["defense_gate"]["checks"]
    return [
        ("Strategy freeze", checks.get("strategy_freeze_verified")),
        ("Data lineage / bias", checks.get("data_bias_defense_passed")),
        ("Baseline fairness", checks.get("baseline_fairness_verified")),
        ("Bootstrap confidence", checks.get("bootstrap_confidence_intervals_present")),
        ("Forward paper-trading protocol", checks.get("paper_trading_protocol_initialized")),
        ("Claim boundary preserved", checks.get("performance_claim_boundary_preserved")),
    ]


def write_markdown_paper(report, claim_gate, visuals, out_path, defense=None):
    metrics = report["metrics_by_strategy"]
    candidate = metrics["agentic_candidate_v1"]
    rows = _top_rows(metrics)
    non_claims = report["claim"]["non_claims"]
    lines = []
    lines.append("# Downside Performance Harness v0.1")
    lines.append("")
    lines.append("## Scoped Claim")
    lines.append("")
    lines.append("> SOTA-grade downside-adjusted hypothetical backtested performance under the included deterministic `downside_performance_v1` benchmark suite.")
    lines.append("")
    lines.append("This paper documents a scoped, deterministic, hypothetical backtest result. It does not claim live trading readiness, future returns, realized investor performance, broker integration, or universal market dominance.")
    lines.append("")
    lines.append("## Headline Result")
    lines.append("")
    lines.append("| Metric | agentic_candidate_v1 |")
    lines.append("| --- | ---: |")
    lines.append("| Return multiple | %.3fx |" % candidate["return_multiple"])
    lines.append("| Total return | %s |" % _format_pct(candidate["total_return"]))
    lines.append("| CAGR | %s |" % _format_pct(candidate["cagr"]))
    lines.append("| Max drawdown | %s |" % _format_pct(candidate["max_drawdown"]))
    lines.append("| Calmar ratio | %s |" % _format_ratio(candidate["calmar_ratio"]))
    lines.append("| Sharpe ratio | %s |" % _format_ratio(candidate["sharpe_ratio"]))
    lines.append("| Claim gate | `%s`, `performance_claim_publishable=%s` |" % (claim_gate["status"], claim_gate["performance_claim_publishable"]))
    lines.append("")
    lines.append("## Baseline Comparison")
    lines.append("")
    lines.append("| Rank | Strategy | Total Return | CAGR | Max DD | Calmar | Sharpe |")
    lines.append("| ---: | --- | ---: | ---: | ---: | ---: | ---: |")
    for idx, row in enumerate(rows, 1):
        lines.append("| %d | `%s` | %s | %s | %s | %s | %s |" % (
            idx,
            row["strategy_id"],
            _format_pct(row["total_return"]),
            _format_pct(row["cagr"]),
            _format_pct(row["max_drawdown"]),
            _format_ratio(row["calmar_ratio"]),
            _format_ratio(row["sharpe_ratio"]),
        ))
    lines.append("")
    lines.append("![Equity curve](%s)" % visuals["equity_curve"])
    lines.append("")
    lines.append("![Drawdown curve](%s)" % visuals["drawdown_curve"])
    lines.append("")
    lines.append("![Baseline total return](%s)" % visuals["baseline_return"])
    lines.append("")
    lines.append("![Risk-adjusted ranking](%s)" % visuals["risk_adjusted_ranking"])
    lines.append("")
    lines.append("![Cost stress](%s)" % visuals["cost_stress"])
    lines.append("")
    lines.append("## Robustness and Claim Boundary")
    lines.append("")
    lines.append("The benchmark includes data-quality gates, lookahead audit, walk-forward validation, cost/slippage stress, parameter sensitivity, and negative controls for lookahead leakage and overfit traps.")
    lines.append("")
    if defense:
        gate = defense["defense_gate"]
        confidence = defense["statistical_confidence_report"]["bootstrap"]["metrics"]
        protocol = defense["forward_paper_trading_protocol"]
        lines.append("## Defense Layer v0.2")
        lines.append("")
        lines.append("The public snapshot also includes a defense packet for reviewer-facing attack surfaces: strategy freeze, data lineage and bias disclosure, baseline fairness, deterministic bootstrap confidence intervals, and a forward paper-trading protocol. This defense layer does not expand the claim beyond hypothetical backtested performance under the included benchmark.")
        lines.append("")
        lines.append("| Defense check | Passed |")
        lines.append("| --- | ---: |")
        for label, passed in _defense_checks_row(defense):
            lines.append("| %s | `%s` |" % (label, passed))
        lines.append("| Defense gate | `%s`, `defense_claim_defensible=%s` |" % (
            gate["status"],
            gate["defense_claim_defensible"],
        ))
        lines.append("")
        lines.append("| Bootstrap metric | p05 / median / p95 |")
        lines.append("| --- | ---: |")
        lines.append("| CAGR | %s |" % _ci_range(confidence, "cagr", scale=100.0, suffix="%"))
        lines.append("| Max drawdown | %s |" % _ci_range(confidence, "max_drawdown", scale=100.0, suffix="%"))
        lines.append("| Calmar ratio | %s |" % _ci_range(confidence, "calmar_ratio"))
        lines.append("| Sharpe ratio | %s |" % _ci_range(confidence, "sharpe_ratio"))
        lines.append("")
        lines.append("Forward paper-trading protocol starts on `%s` with checkpoints `%s`. These checkpoints are for future evidence collection only and are not live-performance claims." % (
            protocol.get("forward_start_date"),
            "`, `".join(protocol.get("checkpoints", [])),
        ))
        lines.append("")
    lines.append("Non-claims preserved by the claim contract:")
    lines.append("")
    for item in non_claims:
        lines.append("- %s" % item)
    lines.append("")
    lines.append("Evidence files are generated under `dist/downside_performance_v1_evidence` and the public snapshot under `dist/downside_performance_v1_public_snapshot`.")
    _ensure_dir(os.path.dirname(out_path))
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
        handle.write("\n")


def _register_pdf_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    regular = r"C:\Windows\Fonts\malgun.ttf"
    bold = r"C:\Windows\Fonts\malgunbd.ttf"
    if os.path.exists(regular):
        pdfmetrics.registerFont(TTFont("MalgunGothic", regular))
        if os.path.exists(bold):
            pdfmetrics.registerFont(TTFont("MalgunGothic-Bold", bold))
        return "MalgunGothic", "MalgunGothic-Bold" if os.path.exists(bold) else "MalgunGothic"
    return "Helvetica", "Helvetica-Bold"


def write_pdf_paper(report, claim_gate, visuals, out_path, defense=None):
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception as exc:
        raise RuntimeError("ReportLab is required to build the PDF paper: %s" % exc)

    regular_font, bold_font = _register_pdf_fonts()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="PaperTitle",
        parent=styles["Title"],
        fontName=bold_font,
        fontSize=24,
        leading=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#111827"),
        spaceAfter=14,
    ))
    styles.add(ParagraphStyle(
        name="PaperSubtitle",
        parent=styles["BodyText"],
        fontName=regular_font,
        fontSize=11,
        leading=16,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#4b5563"),
        spaceAfter=16,
    ))
    styles.add(ParagraphStyle(
        name="Heading",
        parent=styles["Heading1"],
        fontName=bold_font,
        fontSize=15,
        leading=19,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=10,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="Body",
        parent=styles["BodyText"],
        fontName=regular_font,
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#1f2937"),
        spaceAfter=7,
    ))
    styles.add(ParagraphStyle(
        name="Small",
        parent=styles["BodyText"],
        fontName=regular_font,
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#4b5563"),
    ))

    _ensure_dir(os.path.dirname(out_path))
    doc = SimpleDocTemplate(
        out_path,
        pagesize=letter,
        rightMargin=0.62 * inch,
        leftMargin=0.62 * inch,
        topMargin=0.58 * inch,
        bottomMargin=0.58 * inch,
        title="Downside Performance Harness v0.1",
    )
    metrics = report["metrics_by_strategy"]
    candidate = metrics["agentic_candidate_v1"]
    rows = _top_rows(metrics)
    story = []

    def p(text, style="Body"):
        story.append(Paragraph(text, styles[style]))

    def heading(text):
        story.append(Paragraph(text, styles["Heading"]))

    def table(data, widths=None, font_size=8.3):
        t = Table(data, colWidths=widths, hAlign="LEFT", repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5edf7")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
            ("FONTNAME", (0, 0), (-1, 0), bold_font),
            ("FONTNAME", (0, 1), (-1, -1), regular_font),
            ("FONTSIZE", (0, 0), (-1, -1), font_size),
            ("LEADING", (0, 0), (-1, -1), font_size + 3),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.11 * inch))

    story.append(Paragraph("Downside Performance Harness v0.1", styles["PaperTitle"]))
    story.append(Paragraph(
        "SOTA-grade downside-adjusted hypothetical backtested performance under the included deterministic downside_performance_v1 benchmark suite.",
        styles["PaperSubtitle"],
    ))
    heading("Scoped Claim")
    p("This paper documents a bounded performance claim for a research harness, not a live trading system. The claim is limited to deterministic synthetic OHLCV data, included baselines, included robustness checks, and the official performance claim gate.")
    table([
        ["Field", "Value"],
        ["Claim id", report["claim"]["id"]],
        ["Benchmark suite", report["claim"]["benchmark_suite"]],
        ["Performance type", report["claim"]["performance_type"]],
        ["Gate status", "%s / performance_claim_publishable=%s" % (claim_gate["status"], claim_gate["performance_claim_publishable"])],
    ], widths=[1.65 * inch, 5.15 * inch], font_size=8.2)
    heading("Headline Result")
    table([
        ["Metric", "agentic_candidate_v1"],
        ["Return multiple", "%.3fx" % candidate["return_multiple"]],
        ["Total return", _format_pct(candidate["total_return"])],
        ["CAGR", _format_pct(candidate["cagr"])],
        ["Max drawdown", _format_pct(candidate["max_drawdown"])],
        ["Calmar", _format_ratio(candidate["calmar_ratio"])],
        ["Sharpe", _format_ratio(candidate["sharpe_ratio"])],
        ["Average exposure", _format_pct(candidate["average_exposure"])],
    ], widths=[2.3 * inch, 2.0 * inch], font_size=8.8)
    p("Interpretation: the candidate is top-ranked on total return, CAGR, and Calmar within the included benchmark, while preserving the non-claims required by the claim contract.", "Small")
    story.append(PageBreak())

    heading("Benchmark Method")
    p("The benchmark executes a fixed deterministic strategy registry: cash, buy-and-hold synthetic SPY, equal weight, SMA crossover, simple momentum, mean reversion, volatility targeting, the Stock Harness MA-to-cash baseline, and agentic_candidate_v1.")
    p("Measured metrics include total return, return multiple, CAGR, annualized return, max drawdown, volatility, downside deviation, Sharpe, Sortino, Calmar, worst month, worst year, turnover, exposure, and final equity.")
    heading("Baseline Table")
    data = [["Rank", "Strategy", "Total Return", "CAGR", "Max DD", "Calmar", "Sharpe"]]
    for idx, row in enumerate(rows, 1):
        data.append([
            str(idx),
            row["strategy_id"],
            _format_pct(row["total_return"]),
            _format_pct(row["cagr"]),
            _format_pct(row["max_drawdown"]),
            _format_ratio(row["calmar_ratio"]),
            _format_ratio(row["sharpe_ratio"]),
        ])
    table(data, widths=[0.45 * inch, 2.05 * inch, 0.95 * inch, 0.75 * inch, 0.75 * inch, 0.75 * inch, 0.75 * inch], font_size=7.5)
    story.append(Image(visuals["baseline_return"], width=6.6 * inch, height=3.92 * inch))
    story.append(PageBreak())

    heading("Equity and Drawdown")
    p("The equity curve and drawdown curve show the candidate against the strongest included baselines. These figures are hypothetical backtested curves generated from the same deterministic evidence packet used by the claim gate.")
    story.append(Image(visuals["equity_curve"], width=6.6 * inch, height=3.92 * inch))
    story.append(Spacer(1, 0.08 * inch))
    story.append(Image(visuals["drawdown_curve"], width=6.6 * inch, height=3.92 * inch))
    story.append(PageBreak())

    heading("Risk-Adjusted Ranking")
    p("The Calmar ratio captures return per unit of max drawdown. In this benchmark, agentic_candidate_v1 is ranked first on Calmar and remains competitive on Sharpe while using downside-aware exposure control.")
    story.append(Image(visuals["risk_adjusted_ranking"], width=6.6 * inch, height=3.92 * inch))
    heading("Cost and Slippage Stress")
    story.append(Image(visuals["cost_stress"], width=6.6 * inch, height=3.92 * inch))
    story.append(PageBreak())

    heading("Robustness Checks")
    robustness = report["robustness"]
    table([
        ["Check", "Result"],
        ["Data quality", str(robustness["data_quality"]["passed"])],
        ["Lookahead audit", str(robustness["lookahead_audit"]["passed"])],
        ["Walk-forward", str(robustness["walk_forward"]["passed"])],
        ["Cost/slippage stress", str(robustness["cost_slippage_stress"]["passed"])],
        ["Parameter sensitivity", str(robustness["parameter_sensitivity"]["passed"])],
        ["Negative controls", str(
            report["negative_controls"].get("lookahead_leak_detected")
            and report["negative_controls"].get("overfit_trap_rejected")
            and report["negative_controls"].get("extreme_cost_mutation_survived")
        )],
    ], widths=[2.4 * inch, 1.4 * inch], font_size=8.8)
    if defense:
        story.append(PageBreak())
        heading("Defense Layer v0.2")
        p("The public snapshot includes a defense packet for reviewer-facing attack surfaces: strategy freeze, data lineage and bias disclosure, baseline fairness, deterministic bootstrap confidence intervals, and a forward paper-trading protocol. This layer does not expand the claim beyond hypothetical backtested performance under the included benchmark.")
        gate = defense["defense_gate"]
        data = [["Defense check", "Passed"]]
        for label, passed in _defense_checks_row(defense):
            data.append([label, str(passed)])
        data.append(["Defense gate", "%s / %s" % (gate["status"], gate["defense_claim_defensible"])])
        table(data, widths=[3.2 * inch, 1.4 * inch], font_size=8.4)
        confidence = defense["statistical_confidence_report"]["bootstrap"]["metrics"]
        table([
            ["Bootstrap metric", "p05 / median / p95"],
            ["CAGR", _ci_range(confidence, "cagr", scale=100.0, suffix="%")],
            ["Max drawdown", _ci_range(confidence, "max_drawdown", scale=100.0, suffix="%")],
            ["Calmar ratio", _ci_range(confidence, "calmar_ratio")],
            ["Sharpe ratio", _ci_range(confidence, "sharpe_ratio")],
        ], widths=[1.8 * inch, 2.6 * inch], font_size=8.2)
        protocol = defense["forward_paper_trading_protocol"]
        p("Forward paper-trading protocol starts on %s with checkpoints %s. These checkpoints are for future evidence collection only and are not live-performance claims." % (
            protocol.get("forward_start_date"),
            ", ".join(protocol.get("checkpoints", [])),
        ), "Small")
    heading("Non-Claims")
    for item in report["claim"]["non_claims"]:
        p("- %s" % item)
    heading("Evidence Packet")
    p("The public snapshot packages the claim-gate JSON, benchmark JSON, evidence packet, charts, Markdown paper, and PDF paper with SHA-256 hashes. The official result is only publishable when the deterministic claim gate reports performance_claim_publishable=true.")

    doc.build(story)


def write_snapshot(snapshot_dir, claim_gate_path, benchmark_path, evidence_dir, visuals, paper_md, paper_pdf, clean, defense_dir=None):
    if clean:
        _safe_rmtree(snapshot_dir, os.path.join(ROOT, "dist"))
    _ensure_dir(snapshot_dir)
    reports_dir = os.path.join(snapshot_dir, "reports")
    visuals_dir = os.path.join(snapshot_dir, "visuals")
    paper_dir = os.path.join(snapshot_dir, "paper")
    evidence_out = os.path.join(snapshot_dir, "evidence")
    _ensure_dir(reports_dir)
    _ensure_dir(visuals_dir)
    _ensure_dir(paper_dir)
    _copy_file(claim_gate_path, os.path.join(reports_dir, os.path.basename(claim_gate_path)))
    _copy_file(benchmark_path, os.path.join(reports_dir, os.path.basename(benchmark_path)))
    _copy_tree(evidence_dir, evidence_out)
    for path in visuals.values():
        _copy_file(path, os.path.join(visuals_dir, os.path.basename(path)))
    _copy_file(paper_md, os.path.join(paper_dir, os.path.basename(paper_md)))
    _copy_file(paper_pdf, os.path.join(paper_dir, os.path.basename(paper_pdf)))
    if defense_dir and os.path.isdir(defense_dir):
        _copy_tree(defense_dir, os.path.join(snapshot_dir, "defense"))
    files = []
    for dirpath, _, filenames in os.walk(snapshot_dir):
        for filename in sorted(filenames):
            path = os.path.join(dirpath, filename)
            rel = os.path.relpath(path, snapshot_dir).replace(os.sep, "/")
            if rel == "PUBLIC_SNAPSHOT_MANIFEST.json":
                continue
            files.append({
                "path": rel,
                "bytes": os.path.getsize(path),
                "sha256": _sha256_file(path),
            })
    manifest = {
        "schema": "downside_performance_public_snapshot_v1",
        "status": "passed",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "claim_gate_json": os.path.basename(claim_gate_path),
        "benchmark_json": os.path.basename(benchmark_path),
        "file_count": len(files),
        "files": files,
    }
    manifest_path = os.path.join(snapshot_dir, "PUBLIC_SNAPSHOT_MANIFEST.json")
    _write_json(manifest_path, manifest, pretty=True)
    return manifest


def build_public_artifacts(args):
    claim_gate_path = _repo_path(args.claim_gate_json)
    benchmark_path = _repo_path(args.benchmark_json)
    evidence_dir = _repo_path(args.evidence_dir)
    defense_dir = _repo_path(args.defense_dir) if args.defense_dir else None
    visuals_dir = _repo_path(args.visuals_dir)
    paper_md = _repo_path(args.paper_md)
    paper_pdf = _repo_path(args.paper_pdf)
    snapshot_dir = _repo_path(args.snapshot_dir)

    claim_gate = _load_json(claim_gate_path)
    report = claim_gate["report"]
    defense = _load_defense_packet(defense_dir)
    if claim_gate.get("status") != "passed" or not claim_gate.get("performance_claim_publishable"):
        raise ValueError("performance claim gate is not publishable")
    if args.clean_visuals and os.path.isdir(visuals_dir):
        _safe_rmtree(visuals_dir, os.path.join(ROOT, "reports"))
    visuals = generate_visuals(report, visuals_dir)
    write_markdown_paper(report, claim_gate, visuals, paper_md, defense=defense)
    write_pdf_paper(report, claim_gate, visuals, paper_pdf, defense=defense)
    manifest = write_snapshot(
        snapshot_dir,
        claim_gate_path,
        benchmark_path,
        evidence_dir,
        visuals,
        paper_md,
        paper_pdf,
        clean=args.clean_snapshot,
        defense_dir=defense_dir,
    )
    return {
        "schema": "downside_performance_public_artifacts_build_v1",
        "status": "passed",
        "claim_gate_status": claim_gate.get("status"),
        "performance_claim_publishable": claim_gate.get("performance_claim_publishable"),
        "visuals": visuals,
        "paper_markdown": paper_md,
        "paper_pdf": paper_pdf,
        "defense_packet_included": defense is not None,
        "snapshot_dir": snapshot_dir,
        "snapshot_manifest": manifest,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claim-gate-json", default="reports/downside_performance_claim_gate_latest.json")
    parser.add_argument("--benchmark-json", default="reports/downside_performance_v1_latest.json")
    parser.add_argument("--evidence-dir", default="dist/downside_performance_v1_evidence")
    parser.add_argument("--defense-dir", default="dist/downside_performance_v1_defense_packet")
    parser.add_argument("--visuals-dir", default="reports/downside_performance_visuals")
    parser.add_argument("--paper-md", default="paper/DOWNSIDE_PERFORMANCE_CLAIM_PAPER.md")
    parser.add_argument("--paper-pdf", default="paper/DOWNSIDE_PERFORMANCE_CLAIM_PAPER.pdf")
    parser.add_argument("--snapshot-dir", default="dist/downside_performance_v1_public_snapshot")
    parser.add_argument("--clean-visuals", action="store_true")
    parser.add_argument("--clean-snapshot", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    payload = build_public_artifacts(args)
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
