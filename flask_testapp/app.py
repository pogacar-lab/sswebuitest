import os
import time
import random
from flask import Flask, render_template, request, redirect, url_for, abort, jsonify

app = Flask(__name__)


def _make_table_rows(n: int) -> list[dict]:
    statuses = ["完了", "処理中", "待機中", "エラー", "キャンセル"]
    categories = ["注文", "返品", "問い合わせ", "見積", "契約"]
    rows = []
    for i in range(1, n + 1):
        rows.append({
            "id": f"TXN-{i:05d}",
            "date": f"2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
            "category": categories[i % len(categories)],
            "customer": f"顧客_{i:04d}",
            "amount": f"¥{random.randint(1000, 999999):,}",
            "status": statuses[i % len(statuses)],
            "note": f"備考テキスト {i}" if i % 3 == 0 else "",
        })
    return rows


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/slow")
def slow():
    delay = int(request.args.get("delay", 5))
    delay = max(1, min(delay, 30))
    time.sleep(delay)
    return render_template("slow.html", delay=delay)


@app.route("/form", methods=["GET"])
def form():
    return render_template("form.html", submitted=False, data=None)


@app.route("/form", methods=["POST"])
def form_submit():
    data = {
        "username": request.form.get("username", ""),
        "email": request.form.get("email", ""),
        "password": request.form.get("password", ""),
        "age": request.form.get("age", ""),
        "country": request.form.get("country", ""),
        "plan": request.form.get("plan", ""),
        "interests": request.form.getlist("interests"),
        "agree": request.form.get("agree") == "on",
        "newsletter": request.form.get("newsletter") == "on",
        "message": request.form.get("message", ""),
        "birth_date": request.form.get("birth_date", ""),
        "score": request.form.get("score", ""),
    }
    return render_template("form.html", submitted=True, data=data)


@app.route("/table")
def table():
    rows = _make_table_rows(200)
    return render_template("table.html", rows=rows, total=len(rows))


@app.route("/hscroll")
def hscroll():
    columns = [
        "ID", "日付", "担当者", "部門", "プロジェクト", "タスク名", "優先度",
        "開始日", "終了日", "進捗(%)", "予算(万円)", "実績(万円)", "差異(万円)",
        "工数(h)", "残工数(h)", "品質スコア", "レビュアー", "承認者",
        "関連チケット", "最終更新", "コメント",
    ]
    rows = []
    priorities = ["高", "中", "低"]
    depts = ["開発", "営業", "企画", "インフラ", "QA", "デザイン"]
    for i in range(1, 31):
        budget = random.randint(50, 500)
        actual = random.randint(30, 550)
        rows.append({
            "id": f"TASK-{i:04d}",
            "date": f"2024-{(i % 12)+1:02d}-{(i % 28)+1:02d}",
            "owner": f"担当者_{i:02d}",
            "dept": depts[i % len(depts)],
            "project": f"プロジェクト{chr(64 + (i % 8) + 1)}",
            "task": f"タスク名称サンプル {i} - 詳細説明テキスト",
            "priority": priorities[i % len(priorities)],
            "start": f"2024-{(i % 10)+1:02d}-01",
            "end": f"2024-{(i % 10)+2:02d}-28",
            "progress": min(100, i * 4 - 2),
            "budget": budget,
            "actual": actual,
            "diff": budget - actual,
            "hours": random.randint(10, 200),
            "remaining": random.randint(0, 80),
            "quality": round(random.uniform(3.0, 5.0), 1),
            "reviewer": f"レビュアー_{(i % 5)+1:02d}",
            "approver": f"承認者_{(i % 3)+1:02d}",
            "ticket": f"#{random.randint(100, 999)}",
            "updated": f"2024-{(i % 12)+1:02d}-{(i % 28)+1:02d} {i % 24:02d}:00",
            "comment": f"コメントテキスト {i}" if i % 2 == 0 else "",
        })
    return render_template("hscroll.html", columns=columns, rows=rows)


@app.route("/pager")
def pager():
    per_page = 10
    total_rows = _make_table_rows(100)
    total = len(total_rows)
    total_pages = (total + per_page - 1) // per_page
    page = int(request.args.get("page", 1))
    page = max(1, min(page, total_pages))
    rows = total_rows[(page - 1) * per_page: page * per_page]
    return render_template(
        "pager.html",
        rows=rows,
        page=page,
        total_pages=total_pages,
        total=total,
        per_page=per_page,
    )


@app.route("/ajax-table")
def ajax_table():
    delay = int(request.args.get("delay", 3))
    delay = max(0, min(delay, 30))
    return render_template("ajax_table.html", delay=delay)


@app.route("/api/table-data")
def api_table_data():
    delay = int(request.args.get("delay", 3))
    delay = max(0, min(delay, 30))
    time.sleep(delay)
    rows = _make_table_rows(30)
    return jsonify({"rows": rows, "total": len(rows), "delay": delay})


@app.route("/not-found")
def not_found_trigger():
    abort(404)


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug, port=5000)
