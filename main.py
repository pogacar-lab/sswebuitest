from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Optional

import click

from logger import setup_logger
from validator import (
    validate_test_file,
    validate_env_file,
    cross_validate,
    run_dry_run,
    YAMLSyntaxError,
    SchemaValidationError,
    SemanticValidationError,
)
from runner import TestRunner
from reporter import generate_report
from browser import BrowserStartError


def _resolve_env_file(test_file: Path, env_file: Optional[Path]) -> Path:
    if env_file:
        return env_file
    candidate = test_file.parent.parent / "environments" / "env.yaml"
    if candidate.exists():
        return candidate
    raise click.UsageError(
        f"環境定義ファイルが見つかりません。--env-file で指定するか、{candidate} に配置してください。"
    )


@click.group()
def cli():
    """WebuiTest - Selenium を使った Web UI テスト自動化ツール"""


@cli.command("dry-run")
@click.argument("test_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--env-file",
    type=click.Path(path_type=Path),
    default=None,
    help="環境定義YAMLファイルのパス（省略時は environments/env.yaml を自動探索）",
)
@click.option(
    "--env-id",
    default=None,
    help="検証する環境ID（例: chrome_1920x1080）。省略時は env_id の存在チェックをスキップ",
)
def dry_run(test_file: Path, env_file: Optional[Path], env_id: Optional[str]):
    """YAMLファイルの構文・スキーマ検証のみを実行します（ブラウザ起動なし）"""
    logger = setup_logger()

    try:
        resolved_env = _resolve_env_file(test_file, env_file)
    except click.UsageError as e:
        click.echo(f"エラー: {e}", err=True)
        sys.exit(1)

    exit_code = run_dry_run(test_file, resolved_env, env_id=env_id, logger=logger)
    sys.exit(exit_code)


@cli.command("run")
@click.argument("test_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output", "-o",
    required=True,
    type=click.Path(path_type=Path),
    help="ログ・スクリーンショットの出力ディレクトリ",
)
@click.option(
    "--env-file",
    type=click.Path(path_type=Path),
    default=None,
    help="環境定義YAMLファイルのパス（省略時は environments/env.yaml を自動探索）",
)
@click.option(
    "--env-id",
    required=True,
    help="使用する環境ID（例: chrome_1920x1080）",
)
def run(test_file: Path, output: Path, env_file: Optional[Path], env_id: str):
    """テストを実行します"""
    output_dir = output

    logger = setup_logger(log_dir=output_dir)

    try:
        resolved_env = _resolve_env_file(test_file, env_file)
    except click.UsageError as e:
        logger.critical(str(e))
        sys.exit(1)

    # バリデーション
    try:
        scenario = validate_test_file(test_file)
        env_data = validate_env_file(resolved_env)
        cross_validate(env_id, env_data)
    except (YAMLSyntaxError, SchemaValidationError, SemanticValidationError) as e:
        logger.critical(f"設定ファイルのエラー: {e}")
        sys.exit(1)

    env = next(e for e in env_data.environments if e.env_id == env_id)

    # テストYAML を出力ディレクトリへコピー
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(test_file, output_dir / test_file.name)

    # テスト実行
    try:
        runner = TestRunner(scenario, env, output_dir, logger)
        results = runner.run()
    except BrowserStartError as e:
        logger.critical(str(e))
        sys.exit(1)

    # HTML レポート生成
    try:
        report_path = generate_report(
            output_dir=output_dir,
            scenario_name=scenario.scenario_name,
            env_id=env_id,
            results=results,
        )
        logger.info(f"レポート出力: {report_path}")
    except Exception as e:
        logger.warning(f"レポート生成に失敗しました（テスト結果には影響しません）: {e}")

    failed = [r for r in results if not r.passed]
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    cli()
