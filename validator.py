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


def cross_validate(scenario: TestScenario, env_file: EnvironmentFile) -> None:
    nos = {env.env_no for env in env_file.environments}
    if scenario.env_no not in nos:
        raise SemanticValidationError(
            f"env_no={scenario.env_no} が環境定義ファイルに見つかりません (定義済み: {sorted(nos)})"
        )


def run_dry_run(
    test_file: Path,
    env_file: Path,
    logger: Optional[logging.Logger] = None,
) -> int:
    log = logger or logging.getLogger("webuiTest")

    log.info(f"[DRY-RUN] {test_file}")

    # YAML構文チェック
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

    # クロスバリデーション
    try:
        cross_validate(scenario, env_data)
    except SemanticValidationError as e:
        log.error(f"  Cross-validation: NG - {e}")
        return 1

    env = next(e for e in env_data.environments if e.env_no == scenario.env_no)
    log.info(
        f"  env_no={scenario.env_no} → browser={env.browser.value}, "
        f"{env.window_width}x{env.window_height}, headless={env.options.headless}"
    )

    log.info(f"  Test cases: {len(scenario.test_cases)}")
    for i, tc in enumerate(scenario.test_cases, 1):
        log.info(
            f"    [{i:03d}] {tc.name:<30} "
            f"{len(tc.actions)} actions  "
            f"screenshot={tc.screenshot}  scroll={tc.screenshot_scroll}"
        )

    log.info("RESULT: PASSED")
    return 0
