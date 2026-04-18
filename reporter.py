"""HTML レポート生成モジュール

runs.json  : 全ランの結果履歴（JSON）
report.html: 全ランを横並びにした比較表 HTML

差分ルール（直前ランとの比較）:
  changed  : pass/fail が変化した
  new      : 直前ランに存在しなかったケース
  removed  : 今回のランに存在しないが過去ランには存在するケース
  unchanged: 変化なし
  ※ 経過秒数・スクリーンショット画像は比較対象外
"""
from __future__ import annotations

import html as html_mod
import json
from datetime import datetime
from pathlib import Path

from runner import TestResult


def generate_report(
    output_dir: Path,
    scenario_name: str,
    env_id: str,
    results: list[TestResult],
    timestamp: datetime,
) -> Path:
    """runs.json を更新し report.html を生成して返す。"""
    runs_path = output_dir / "runs.json"
    report_path = output_dir / "report.html"

    # 既存の履歴を読み込む
    all_runs: list[dict] = []
    if runs_path.exists():
        try:
            with open(runs_path, encoding="utf-8") as f:
                all_runs = json.load(f)
        except (json.JSONDecodeError, OSError):
            all_runs = []

    # 今回のラン情報を追加
    run_entry = {
        "run_id": len(all_runs) + 1,
        "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "scenario_name": scenario_name,
        "env_id": env_id,
        "results": [
            {
                "name": r.name,
                "passed": r.passed,
                "error": r.error,
                "duration": round(r.duration_seconds, 2),
                "screenshots": [
                    str(p.relative_to(output_dir)).replace("\\", "/")
                    for p in r.screenshot_paths
                ],
            }
            for r in results
        ],
    }
    all_runs.append(run_entry)

    # runs.json 保存
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(runs_path, "w", encoding="utf-8") as f:
        json.dump(all_runs, f, ensure_ascii=False, indent=2)

    # HTML 生成・保存
    html_content = _build_html(all_runs)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return report_path


# ── 内部ユーティリティ ─────────────────────────────────────────────────────────

def _find_result(case_name: str, run: dict) -> dict | None:
    for r in run["results"]:
        if r["name"] == case_name:
            return r
    return None


def _row_diff_class(case_name: str, all_runs: list[dict]) -> str:
    """直前ランとの pass/fail・error を比較してテーブル行のクラスを返す。
    比較対象: passed, error のみ（経過秒数・画像は対象外）
    """
    if len(all_runs) < 2:
        return "row-new"

    latest = _find_result(case_name, all_runs[-1])
    prev = _find_result(case_name, all_runs[-2])

    if prev is None and latest is not None:
        return "row-new"
    if prev is not None and latest is None:
        return "row-removed"
    if latest is None:
        return "row-absent"
    if prev["passed"] != latest["passed"]:
        return "row-changed"
    return "row-unchanged"


def _cell_html(result: dict | None, is_latest: bool) -> str:
    if result is None:
        return '<td class="cell-absent">—</td>'

    status_cls = "cell-pass" if result["passed"] else "cell-fail"
    latest_cls = " cell-latest" if is_latest else ""
    badge = "✓ PASS" if result["passed"] else "✗ FAIL"

    parts: list[str] = [
        f'<span class="badge">{badge}</span>'
        f'<span class="duration">{result["duration"]}s</span>',
    ]

    if result.get("error"):
        err = html_mod.escape(result["error"][:300])
        parts.append(f'<div class="error-msg">{err}</div>')

    for ss in result.get("screenshots", []):
        ss_e = html_mod.escape(ss)
        parts.append(
            f'<a href="{ss_e}" target="_blank">'
            f'<img src="{ss_e}" alt="{ss_e}" loading="lazy">'
            f'</a>'
        )

    inner = "\n".join(parts)
    return f'<td class="{status_cls}{latest_cls}">{inner}</td>'


def _build_html(all_runs: list[dict]) -> str:
    scenario_name = all_runs[-1]["scenario_name"] if all_runs else ""

    # テストケース名を収集
    # 最新ランの順序を優先し、削除済みケースを末尾に追加
    case_names: list[str] = []
    seen: set[str] = set()
    if all_runs:
        for r in all_runs[-1]["results"]:
            if r["name"] not in seen:
                case_names.append(r["name"])
                seen.add(r["name"])
    for run in all_runs[:-1]:
        for r in run["results"]:
            if r["name"] not in seen:
                case_names.append(r["name"])
                seen.add(r["name"])

    # ── ヘッダ行 ──────────────────────────────────────────────────────────────
    run_headers: list[str] = []
    for i, run in enumerate(all_runs):
        is_latest = i == len(all_runs) - 1
        th_cls = ' class="th-latest"' if is_latest else ""
        passed = sum(1 for r in run["results"] if r["passed"])
        total = len(run["results"])
        label = "★ 最新 " if is_latest else ""
        run_headers.append(
            f'<th{th_cls}>'
            f'{label}Run {run["run_id"]}<br>'
            f'<small>{html_mod.escape(run["timestamp"])}</small><br>'
            f'<small>{html_mod.escape(run["env_id"])}</small><br>'
            f'<span class="run-summary">{passed}/{total} PASS</span>'
            f'</th>'
        )

    # ── データ行 ──────────────────────────────────────────────────────────────
    rows: list[str] = []
    for case_name in case_names:
        row_cls = _row_diff_class(case_name, all_runs)
        cells = [f'<td class="case-name">{html_mod.escape(case_name)}</td>']
        for i, run in enumerate(all_runs):
            result = _find_result(case_name, run)
            cells.append(_cell_html(result, is_latest=(i == len(all_runs) - 1)))
        rows.append(f'<tr class="{row_cls}">{"".join(cells)}</tr>')

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WebuiTest Report – {html_mod.escape(scenario_name)}</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: system-ui, -apple-system, sans-serif; font-size: 13px; color: #333; background: #f0f2f5; }}

/* ── ヘッダ ── */
h1 {{ padding: 14px 20px; background: #2c3e50; color: #fff; font-size: 17px; letter-spacing: .3px; }}
.meta {{
  padding: 7px 20px; background: #fff; border-bottom: 1px solid #ddd;
  color: #666; font-size: 11px; display: flex; gap: 16px; flex-wrap: wrap;
}}

/* ── 凡例 ── */
.legend {{
  display: flex; gap: 14px; padding: 8px 20px;
  background: #fff; border-bottom: 1px solid #ddd; flex-wrap: wrap;
}}
.legend-item {{ display: flex; align-items: center; gap: 5px; font-size: 11px; color: #555; }}
.lb {{ width: 4px; height: 14px; border-radius: 2px; flex-shrink: 0; }}
.lb-changed   {{ background: #e67e22; }}
.lb-new       {{ background: #2980b9; }}
.lb-removed   {{ background: #95a5a6; }}
.lb-unchanged {{ background: #ddd; }}

/* ── テーブル ── */
.table-wrap {{ overflow-x: auto; padding: 16px; }}
table {{
  border-collapse: collapse; background: #fff;
  box-shadow: 0 1px 4px rgba(0,0,0,.1); min-width: 500px;
}}
th, td {{ border: 1px solid #dde; padding: 7px 10px; vertical-align: top; }}
th {{
  background: #2c3e50; color: #fff; font-weight: 600;
  white-space: nowrap; text-align: center; line-height: 1.6;
}}
th.th-latest {{ background: #1a5276; }}
.run-summary {{
  display: inline-block; margin-top: 3px; font-size: 11px;
  background: rgba(255,255,255,.2); border-radius: 3px; padding: 1px 6px;
}}

/* ── 行のステータス表示（左ボーダー） ── */
tr.row-changed   td.case-name {{ border-left: 4px solid #e67e22; }}
tr.row-new       td.case-name {{ border-left: 4px solid #2980b9; }}
tr.row-removed   td.case-name {{ border-left: 4px solid #95a5a6; opacity: .65; }}
tr.row-unchanged td.case-name {{ border-left: 4px solid transparent; }}
tr.row-absent    td.case-name {{ border-left: 4px solid transparent; }}

/* ── ケース名列 ── */
td.case-name {{
  font-weight: 600; white-space: nowrap;
  min-width: 150px; background: #fafafa;
}}

/* ── セル背景 ── */
td.cell-pass   {{ background: #eafaf1; }}
td.cell-fail   {{ background: #fdedec; }}
td.cell-absent {{ background: #f5f5f5; color: #bbb; text-align: center; }}
td.cell-latest {{ filter: brightness(0.95); }}

/* ── バッジ・詳細 ── */
.badge {{
  display: inline-block; padding: 1px 7px; border-radius: 3px;
  font-size: 11px; font-weight: bold; color: #fff; vertical-align: middle;
}}
td.cell-pass .badge {{ background: #27ae60; }}
td.cell-fail .badge {{ background: #e74c3c; }}
.duration {{ margin-left: 6px; font-size: 11px; color: #888; vertical-align: middle; }}
.error-msg {{
  margin-top: 5px; font-size: 11px; color: #c0392b;
  background: #fff8f8; border-left: 3px solid #e74c3c;
  padding: 3px 7px; word-break: break-all; line-height: 1.5;
}}

/* ── サムネイル ── */
td a img {{
  display: block; max-width: 180px; margin-top: 6px;
  border: 1px solid #ccc; border-radius: 2px;
  transition: box-shadow .15s;
}}
td a img:hover {{ box-shadow: 0 2px 8px rgba(0,0,0,.25); }}

/* ── 行ホバー ── */
tbody tr:hover td {{ filter: brightness(0.97); }}
</style>
</head>
<body>
<h1>WebuiTest Report – {html_mod.escape(scenario_name)}</h1>
<div class="meta">
  <span>生成日時: {generated_at}</span>
  <span>実行回数: {len(all_runs)} 回</span>
  <span>※ 行左端の色は直前ラン比較（経過秒数・画像を除く）</span>
</div>
<div class="legend">
  <span class="legend-item"><span class="lb lb-changed"></span>直前ランから変化</span>
  <span class="legend-item"><span class="lb lb-new"></span>新規ケース</span>
  <span class="legend-item"><span class="lb lb-removed"></span>削除ケース</span>
  <span class="legend-item"><span class="lb lb-unchanged"></span>変化なし</span>
</div>
<div class="table-wrap">
<table>
<thead>
<tr>
  <th>テストケース</th>
  {"".join(run_headers)}
</tr>
</thead>
<tbody>
{"".join(rows)}
</tbody>
</table>
</div>
</body>
</html>"""
