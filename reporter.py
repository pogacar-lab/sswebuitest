"""HTML レポート生成モジュール

report.html を毎回上書き生成する。
同じシナリオを複数回実行したとき、経過秒数・スクリーンショット画像を除いて
HTML の構造・内容が一致するよう、実行開始時刻などの揮発的なメタ情報は出力しない。
"""
from __future__ import annotations

import html as html_mod
from pathlib import Path

from runner import TestResult


def generate_report(
    output_dir: Path,
    scenario_name: str,
    env_id: str,
    results: list[TestResult],
) -> Path:
    """report.html を生成して返す（毎回上書き）。"""
    report_path = output_dir / "report.html"
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(_build_html(scenario_name, env_id, results, output_dir))
    return report_path


# ── 内部ユーティリティ ─────────────────────────────────────────────────────────

def _build_html(
    scenario_name: str,
    env_id: str,
    results: list[TestResult],
    output_dir: Path,
) -> str:
    rows: list[str] = []
    for idx, r in enumerate(results, 1):
        status_cls = "pass" if r.passed else "fail"
        badge = "✓ PASS" if r.passed else "✗ FAIL"

        # エラーメッセージ
        error_html = ""
        if r.error:
            err = html_mod.escape(r.error)
            error_html = f'<div class="error-msg">{err}</div>'

        # スクリーンショット
        ss_html_parts: list[str] = []
        for p in r.screenshot_paths:
            rel = str(p.relative_to(output_dir)).replace("\\", "/")
            rel_e = html_mod.escape(rel)
            fname = html_mod.escape(p.name)
            ss_html_parts.append(
                f'<a href="{rel_e}" target="_blank" title="{fname}">'
                f'<img src="{rel_e}" alt="{fname}" loading="lazy">'
                f'</a>'
            )
        ss_html = "\n".join(ss_html_parts)

        rows.append(f"""<tr class="{status_cls}">
  <td class="num">{idx:03d}</td>
  <td class="name">{html_mod.escape(r.name)}</td>
  <td class="status"><span class="badge">{badge}</span></td>
  <td class="duration">{r.duration_seconds:.2f}s</td>
  <td class="detail">{error_html}{ss_html}</td>
</tr>""")

    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    summary_cls = "summary-all-pass" if failed == 0 else "summary-has-fail"

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WebuiTest Report – {html_mod.escape(scenario_name)}</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: system-ui, -apple-system, sans-serif; font-size: 13px; color: #333; background: #f0f2f5; }}

h1 {{ padding: 14px 20px; background: #2c3e50; color: #fff; font-size: 17px; }}
.subtitle {{ padding: 6px 20px; background: #34495e; color: #bdc3c7; font-size: 12px; }}

.summary {{
  display: inline-flex; gap: 20px; align-items: center;
  margin: 14px 20px; padding: 10px 18px;
  background: #fff; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,.1);
}}
.summary-all-pass .total {{ color: #27ae60; font-weight: bold; }}
.summary-has-fail .total {{ color: #e74c3c; font-weight: bold; }}
.summary span {{ font-size: 13px; }}
.cnt-pass {{ color: #27ae60; }}
.cnt-fail {{ color: #e74c3c; }}

.table-wrap {{ overflow-x: auto; padding: 0 16px 20px; }}
table {{ border-collapse: collapse; background: #fff; box-shadow: 0 1px 4px rgba(0,0,0,.1); width: 100%; }}
th, td {{ border: 1px solid #dde; padding: 7px 10px; vertical-align: top; }}
th {{ background: #2c3e50; color: #fff; font-weight: 600; white-space: nowrap; }}

td.num      {{ width: 46px; text-align: center; color: #999; font-size: 11px; }}
td.name     {{ font-weight: 600; white-space: nowrap; min-width: 160px; }}
td.status   {{ width: 90px; text-align: center; }}
td.duration {{ width: 72px; text-align: right; color: #777; font-size: 12px; white-space: nowrap; }}
td.detail   {{ min-width: 200px; }}

tr.pass td  {{ background: #eafaf1; }}
tr.fail td  {{ background: #fdedec; }}

.badge {{
  display: inline-block; padding: 2px 8px; border-radius: 3px;
  font-size: 11px; font-weight: bold; color: #fff;
}}
tr.pass .badge {{ background: #27ae60; }}
tr.fail .badge {{ background: #e74c3c; }}

.error-msg {{
  font-size: 11px; color: #c0392b; background: #fff8f8;
  border-left: 3px solid #e74c3c; padding: 3px 7px;
  margin-bottom: 5px; word-break: break-all; line-height: 1.5;
}}

td a img {{
  display: inline-block; max-width: 180px; margin: 3px 4px 0 0;
  border: 1px solid #ccc; border-radius: 2px; vertical-align: top;
  transition: box-shadow .15s;
}}
td a img:hover {{ box-shadow: 0 2px 8px rgba(0,0,0,.25); }}

tbody tr:hover td {{ filter: brightness(0.96); }}
</style>
</head>
<body>
<h1>WebuiTest Report – {html_mod.escape(scenario_name)}</h1>
<div class="subtitle">{html_mod.escape(env_id)}</div>
<div class="summary {summary_cls}">
  <span class="total">{passed}/{len(results)} PASS</span>
  <span class="cnt-pass">✓ {passed} 成功</span>
  <span class="cnt-fail">✗ {failed} 失敗</span>
</div>
<div class="table-wrap">
<table>
<thead>
<tr>
  <th>#</th>
  <th>テストケース</th>
  <th>結果</th>
  <th>経過時間</th>
  <th>詳細 / スクリーンショット</th>
</tr>
</thead>
<tbody>
{"".join(rows)}
</tbody>
</table>
</div>
</body>
</html>"""
