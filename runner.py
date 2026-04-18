from __future__ import annotations

import re
import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from schema import Environment, TestCase, TestScenario
from browser import BrowserManager, BrowserStartError
from actions import execute_action, ActionError
from screenshot import take_screenshot, take_scroll_screenshot, ScreenshotError
from logger import get_logger


@dataclass
class TestResult:
    name: str
    passed: bool
    error: Optional[str] = None
    screenshot_path: Optional[Path] = None
    duration_seconds: float = 0.0


class TestRunner:
    def __init__(
        self,
        scenario: TestScenario,
        env: Environment,
        output_dir: Path,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._scenario = scenario
        self._env = env
        self._output_dir = output_dir
        self._logger = logger or get_logger()

    def run(self) -> list[TestResult]:
        screenshot_dir = self._output_dir / f"env_{self._env.env_no}"
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        self._logger.info(
            f"=== テスト開始: {self._scenario.scenario_name} "
            f"({len(self._scenario.test_cases)} ケース) ==="
        )

        results: list[TestResult] = []

        try:
            with BrowserManager(self._env) as browser:
                for i, tc in enumerate(self._scenario.test_cases, 1):
                    result = self._run_test_case(tc, i, browser, screenshot_dir)
                    results.append(result)

                    if not result.passed and not self._scenario.continue_on_error:
                        self._logger.error("continue_on_error=False のため実行を中断します")
                        break
        except BrowserStartError as e:
            self._logger.critical(str(e))
            raise

        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        self._logger.info(
            f"=== テスト完了: 合計={len(results)} 成功={passed} 失敗={failed} ==="
        )

        return results

    def _run_test_case(
        self,
        tc: TestCase,
        index: int,
        browser: BrowserManager,
        screenshot_dir: Path,
    ) -> TestResult:
        driver = browser.get_driver()
        result = TestResult(name=tc.name, passed=True)

        self._logger.info(f"[{index:03d}] 開始: {tc.name}")
        start_time = time.monotonic()

        try:
            driver.get(tc.entry_url)
            self._logger.debug(f"  URL: {tc.entry_url}")

            for action in tc.actions:
                self._logger.debug(f"  アクション: {action.type} → {action.selector}")
                try:
                    execute_action(driver, action)
                except ActionError as e:
                    self._logger.error(f"  アクション失敗: {e}")
                    result.passed = False
                    result.error = str(e)
                    self._take_error_screenshot(driver, tc, index, screenshot_dir, result)
                    return result

            if tc.screenshot or tc.screenshot_scroll:
                path = screenshot_dir / self._screenshot_filename(index, tc.name)
                try:
                    if tc.screenshot_scroll:
                        take_scroll_screenshot(driver, path)
                    else:
                        take_screenshot(driver, path)
                    result.screenshot_path = path
                    self._logger.info(f"  スクリーンショット保存: {path.name}")
                except ScreenshotError as e:
                    self._logger.warning(f"  スクリーンショット失敗（テスト継続）: {e}")

            if tc.wait:
                time.sleep(tc.wait)

        except Exception as e:
            self._logger.error(f"  予期しないエラー: {e}")
            result.passed = False
            result.error = str(e)
            self._take_error_screenshot(driver, tc, index, screenshot_dir, result)
        finally:
            result.duration_seconds = time.monotonic() - start_time
            status = "成功" if result.passed else "失敗"
            self._logger.info(
                f"[{index:03d}] 完了: {tc.name} [{status}] ({result.duration_seconds:.2f}s)"
            )

        return result

    def _take_error_screenshot(
        self,
        driver,
        tc: TestCase,
        index: int,
        screenshot_dir: Path,
        result: TestResult,
    ) -> None:
        error_path = screenshot_dir / self._screenshot_filename(index, tc.name, error=True)
        try:
            take_screenshot(driver, error_path)
            result.screenshot_path = error_path
            self._logger.info(f"  エラー時スクリーンショット保存: {error_path.name}")
        except ScreenshotError as e:
            self._logger.warning(f"  エラー時スクリーンショット失敗: {e}")

    def _screenshot_filename(self, index: int, name: str, error: bool = False) -> str:
        safe_name = re.sub(r"[^\w]", "_", name)
        suffix = "_ERROR" if error else ""
        return f"{index:03d}_{safe_name}{suffix}.jpg"
