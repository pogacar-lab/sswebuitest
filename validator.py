from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError

from schema import EnvironmentFile, TestScenario


class WebuiTestError(Exception):
    pass


class YAMLSyntaxError(WebuiTestError):
    pass


class SchemaValidationError(WebuiTestError):
    pass


class SemanticValidationError(WebuiTestError):
    pass


def load_yaml_safe(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data or {}
    except yaml.YAMLError as e:
        raise YAMLSyntaxError(str(e)) from e


def validate_test_file(path: Path) -> TestScenario:
    data = load_yaml_safe(path)
    try:
        return TestScenario.model_validate(data)
    except ValidationError as e:
        raise SchemaValidationError(str(e)) from e


def validate_env_file(path: Path) -> EnvironmentFile:
    data = load_yaml_safe(path)
    try:
        return EnvironmentFile.model_validate(data)
    except ValidationError as e:
        raise SchemaValidationError(str(e)) from e


def cross_validate(env_id: str, env_file: EnvironmentFile) -> None:
    ids = {env.env_id for env in env_file.environments}
    if env_id not in ids:
        raise SemanticValidationError(
            f"env_id='{env_id}' が環境定義ファイルに見つかりません "
            f"(定義済み: {sorted(ids)})"
        )


def run_dry_run(
    test_file: Path,
    env_file: Path,
    env_id: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
) -> int:
    log = logger or logging.getLogger("webuiTest")

    log.info(f"[DRY-RUN] {test_file}")

    # テストYAML 構文・スキーマチェック
    try:
        scenario = validate_test_file(test_file)
    except YAMLSyntaxError as e:
        log.error(f"  YAML syntax: NG\n{e}")
        return 1
    except SchemaValidationError as e:
        log.error(f"  YAML syntax: OK")
        log.error(f"  Schema:      NG\n{e}")
        return 1
    log.info("  YAML syntax: OK")
    log.info("  Schema:      OK")

    # 環境定義ファイルのチェック
    try:
        env_data = validate_env_file(env_file)
    except YAMLSyntaxError as e:
        log.error(f"  Env file YAML syntax: NG\n{e}")
        return 1
    except SchemaValidationError as e:
        log.error(f"  Env file YAML syntax: OK")
        log.error(f"  Env file Schema:      NG\n{e}")
        return 1

    # --env-id が指定された場合のみクロスバリデーション
    if env_id is not None:
        try:
            cross_validate(env_id, env_data)
        except SemanticValidationError as e:
            log.error(f"  Cross-validation: NG - {e}")
            return 1
        env = next(e for e in env_data.environments if e.env_id == env_id)
        log.info(
            f"  env_id='{env_id}' → browser={env.browser.value}, "
            f"{env.window_width}x{env.window_height}, headless={env.options.headless}"
        )
    else:
        ids = sorted(e.env_id for e in env_data.environments)
        log.info(f"  利用可能な env_id: {ids}")

    log.info(f"  Test cases: {len(scenario.test_cases)}")
    for i, tc in enumerate(scenario.test_cases, 1):
        ss_actions = [a for a in tc.actions if a.type == "screenshot"]
        other_actions = [a for a in tc.actions if a.type != "screenshot"]
        url_info = tc.entry_url if tc.entry_url else "(継続)"
        window_info = f"  window={tc.window}" if tc.window else ""

        if ss_actions:
            ss_info = f"{len(ss_actions)} screenshots"
        else:
            ss_info = f"screenshot={tc.screenshot}  scroll={tc.screenshot_scroll}"

        log.info(
            f"    [{i:03d}] {tc.name:<30} "
            f"url={url_info}  "
            f"{len(other_actions)} actions  "
            f"{ss_info}"
            f"{window_info}"
        )

    log.info("RESULT: PASSED")
    return 0
