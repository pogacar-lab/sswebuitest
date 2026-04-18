# WebuiTest

Selenium を使った Python 製 Web UI テスト自動化ツールです。
YAML ファイルでテストシナリオを記述し、`run`（実行）と `dry-run`（構文チェック）の 2 モードで動作します。

---

## ディレクトリ構成

```
WebuiTest/
├── main.py                  # CLI エントリーポイント
├── schema.py                # Pydantic v2 データモデル
├── validator.py             # YAML バリデーション（dry-run）
├── browser.py               # WebDriver 管理（Chrome / Firefox / Edge）
├── actions.py               # アクション実行（click / input / select / check）
├── screenshot.py            # スクリーンショット（通常・スクロール合成）
├── runner.py                # テスト実行オーケストレーション
├── logger.py                # ロギング設定
├── requirements.txt         # 依存パッケージ
│
├── environments/
│   ├── env.yaml             # 使用中の環境定義
│   └── env_sample.yaml      # 環境定義サンプル（Chrome / Firefox / Edge）
│
├── tests/
│   ├── webuiapp_fullscreen.yaml   # サンプルアプリ用テスト（1920×1080）
│   ├── webuiapp_half.yaml         # サンプルアプリ用テスト（960×1080）
│   └── sample_test.yaml           # 汎用サンプル
│
└── flask_testapp/           # 動作検証用サンプル Flask アプリ
    ├── app.py
    ├── requirements.txt
    ├── start.cmd            # 起動用バッチ
    └── templates/
        ├── base.html
        ├── index.html       # トップページ（ページ一覧）
        ├── form.html        # フォーム一式
        ├── table.html       # 縦長テーブル（200行）
        ├── hscroll.html     # 横スクロールテーブル（21列）
        ├── pager.html       # ページャ付きテーブル（100件 / 10件ずつ）
        ├── slow.html        # 遅延レスポンス（?delay=N 秒）
        ├── ajax_table.html  # JS fetch による非同期テーブル取得
        └── 404.html         # 404 エラーページ
```

---

## セットアップ

```bash
# 仮想環境の作成・有効化
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac / Linux

# テストツール + Flask アプリの依存パッケージを一括インストール
pip install -r requirements.txt -r flask_testapp/requirements.txt
```

---

## 使い方

### dry-run（YAML 構文・スキーマチェック）

ブラウザを起動せずに YAML ファイルの構文・スキーマを検証します。`--env-id` を指定すると環境の整合性も確認します。

```bash
# 環境 ID を指定して検証
python main.py dry-run tests/webuiapp_fullscreen.yaml --env-id chrome_1920x1080

# env-id を省略した場合は利用可能な env_id 一覧を表示
python main.py dry-run tests/webuiapp_fullscreen.yaml
```

出力例（`--env-id` 指定あり）：

```
[DRY-RUN] tests\webuiapp_fullscreen.yaml
  YAML syntax: OK
  Schema:      OK
  env_id=chrome_1920x1080 → browser=chrome, 1920x1080, headless=False
  Test cases: 9
    [001] top_page                       0 actions  screenshot=True  scroll=False
    [002] form_submit                   11 actions  screenshot=True  scroll=False
    ...
RESULT: PASSED
```

出力例（`--env-id` 省略）：

```
[DRY-RUN] tests\webuiapp_fullscreen.yaml
  YAML syntax: OK
  Schema:      OK
  利用可能な env_id: chrome_1920x1080, chrome_960x1080
  Test cases: 9
    ...
RESULT: PASSED
```

### run（テスト実行）

`--env-id` は必須オプションです。

```bash
python main.py run tests/webuiapp_fullscreen.yaml \
  --output results/fullscreen \
  --env-id chrome_1920x1080 \
  --env-file environments/env.yaml
```

`--env-file` を省略した場合、テストファイルと同階層の `../environments/env.yaml` を自動探索します。

### 出力ディレクトリ構造

```
results/
└── fullscreen/
    ├── test_run.log               # 実行ログ（タイムスタンプ付き）
    └── chrome_1920x1080/
        ├── 001_top_page.jpg
        ├── 002_form_submit.jpg
        ├── 003_table_scroll.jpg   # スクロール合成画像
        ├── ...
        └── 009_error_404.jpg
```

スクリーンショットのファイル名は `{3桁連番}_{テストケース名}.jpg`、エラー時は末尾に `_ERROR` が付きます。

---

## YAML 仕様

### テストケースファイル

```yaml
app_name: "アプリ名"
description: "テストの説明"
scenario_name: "scenario_id"
continue_on_error: false        # true: 失敗しても次のケースへ続行
                                # 使用環境は実行時に --env-id で指定

test_cases:
  - name: ケース名
    entry_url: "http://localhost:5000/form"
    screenshot: true             # 通常スクリーンショット
    screenshot_scroll: false     # true: 全ページスクロール合成撮影
    wait: 1.0                    # 全アクション完了後の待機秒数（省略可）
    actions:
      - type: input
        selector: "#username"
        value: "テスト太郎"
        wait: 0.3                # このアクション後の待機秒数（省略可）
      - type: select
        selector: "#country"
        value: "jp"              # option の value 属性 or 表示テキスト
      - type: click
        selector: "#btn-submit"
      - type: check
        selector: "#agree"
        checked: true
```

#### アクション一覧

| type | 説明 | 必須パラメータ |
|---|---|---|
| `click` | 要素をクリック | `selector` |
| `input` | テキストを入力（既存値をクリア後） | `selector`, `value` |
| `select` | ドロップダウンを選択 | `selector`, `value`（value 属性→表示テキストの順で試行） |
| `check` | チェックボックスのオン/オフ | `selector`, `checked`（bool） |

セレクタは CSS セレクタ（`#id`, `.class`, `button[type='submit']`）と XPath（`/` または `(` 始まり）の両方に対応しています。

### 環境定義ファイル

```yaml
environments:
  - env_id: chrome_1920x1080    # 実行時に --env-id で指定する識別子
    browser: chrome             # chrome / firefox / edge
    window_width: 1920
    window_height: 1080
    options:
      headless: false
      zoom: 1.0
      compatibility_mode: false

  - env_id: chrome_1280x800_headless
    browser: chrome
    window_width: 1280
    window_height: 800
    options:
      headless: true
      zoom: 1.0
      compatibility_mode: false
```

---

## 動作検証用 Flask アプリ

テストツールの動作検証に使える各種ページを提供するサンプルアプリです。

### 起動方法

```bash
# バッチファイルで起動（エラー時に自動 pause）
flask_testapp\start.cmd

# または直接実行
python flask_testapp/app.py
# → http://localhost:5000 で起動
```

### ページ一覧

| URL | 内容 |
|---|---|
| `/` | トップページ（各ページへのリンク） |
| `/form` | フォーム一式（text / email / password / number / date / select / radio / checkbox / textarea） |
| `/table` | 縦長テーブル（200行、`screenshot_scroll` 検証用） |
| `/hscroll` | 横スクロールテーブル（30行 × 21列、左端列固定） |
| `/pager?page=N` | ページャ付きテーブル（100件 / 10件ずつ） |
| `/slow?delay=N` | 遅延レスポンス（N 秒 / デフォルト 5 秒、最大 30 秒） |
| `/ajax-table?delay=N` | JS fetch による非同期テーブル取得（N 秒遅延後に DOM 生成） |
| `/not-found` | 404 エラーページ |
| `/api/table-data?delay=N` | `/ajax-table` 向け JSON API |

各ページの要素には `id` 属性が付与されているため、テスト YAML のセレクタに `#id名` で指定できます。

---

## サンプルテストケース（Flask アプリ向け）

| ファイル | 推奨 env_id | ウィンドウサイズ |
|---|---|---|
| `tests/webuiapp_fullscreen.yaml` | `chrome_1920x1080` | 1920 × 1080（全画面） |
| `tests/webuiapp_half.yaml` | `chrome_960x1080` | 960 × 1080（Windows スナップ右半分） |

どちらも同じ 9 ケースを含みます：

| # | ケース名 | 内容 |
|---|---|---|
| 001 | top_page | トップページのスクリーンショット |
| 002 | form_submit | フォーム入力・送信・結果確認 |
| 003 | table_scroll | 縦長テーブルの全ページスクロール合成撮影 |
| 004 | slow_3sec | 3 秒遅延ページ（`driver.get()` がサーバー応答まで待機） |
| 005 | hscroll_table | 横スクロールテーブルのスクリーンショット |
| 006 | pager_page1 | ページャ 1 ページ目確認 |
| 007 | pager_navigation | ページ遷移（1→3→4→3→最終ページ） |
| 008 | ajax_table_3sec | 非同期テーブル取得（`#arow-1` の DOM 出現を WebDriverWait で待機） |
| 009 | error_404 | 404 エラーページのスクリーンショット |

実行コマンド：

```bash
python main.py run tests/webuiapp_fullscreen.yaml --output results/fullscreen --env-id chrome_1920x1080
python main.py run tests/webuiapp_half.yaml       --output results/half       --env-id chrome_960x1080
```

---

## 依存パッケージ

| パッケージ | 用途 |
|---|---|
| selenium | ブラウザ操作 |
| webdriver-manager | ChromeDriver / GeckoDriver の自動管理 |
| pydantic v2 | YAML スキーマ検証・データモデル |
| pyyaml | YAML 読み込み |
| Pillow | スクリーンショットの JPEG 変換・スクロール合成 |
| click | CLI インターフェース |
| flask | 動作検証用サンプルアプリ |
