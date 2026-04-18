from __future__ import annotations

import re
import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from schema import Environment, TestCase, TestScenario, ScreenshotAction
from browser import BrowserManager, BrowserStartError
from actions import execute_action, ActionError, WindowContext
from screenshot import take_screenshot, take_scroll_screenshot, ScreenshotError
from logger import get_logger


@dataclass
class TestResult:
    name: str
    passed: bool
    error: Optional[str] = None
    screenshot_paths: list[Path] = field(default_factory=list)
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
        screenshot_dir = self._output_dir / self._env.env_id
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        self._logger.info(
            f"=== テスト開始: {self._scenario.scenario_name} "
            f"({len(self._scenario.test_cases)} ケース) ==="
        )

        results: list[TestResult] = []
        ctx = WindowContext()  # セッション全体でウィンドウ別名・スタックを共有

        try:
            with BrowserManager(self._env) as browser:
                for i, tc in enumerate(self._scenario.test_cases, 1):
                    result = self._run_test_case(tc, i, browser, screenshot_dir, ctx)
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
        ctx: WindowContext,
    ) -> TestResult:
        driver = browser.get_driver()
        result = TestResult(name=tc.name, passed=True)
        ss_counter = 0  # このテストケース内のスクショ連番（type: screenshot の個数）

        self._logger.info(f"[{index:03d}] 開始: {tc.name}")
        start_time = time.monotonic()

        try:
            # window プロパティ: 指定された別名のウィンドウへ切り替え（前提チェック込み）
            if tc.window:
                alias = tc.window
                if alias not in ctx.registry:
                    raise RuntimeError(f"ウィンドウ '{alias}' が登録されていません")
                target_handle = ctx.registry[alias]
                if target_handle not in driver.window_handles:
                    raise RuntimeError(f"ウィンドウ '{alias}' はすでに閉じられています")
                if driver.current_window_handle != target_handle:
                    driver.switch_to.window(target_handle)
                    self._logger.debug(f"  ウィンドウ切り替え: {alias}")

            # entry_url: 省略時は現在のウィンドウ状態を引き継ぐ
            if tc.entry_url:
                driver.get(tc.entry_url)
                self._logger.debug(f"  URL: {tc.entry_url}")

            # アクション実行ループ
            for action in tc.actions:
                if isinstance(action, ScreenshotAction):
                    # スクリーンショットアクション: インラインで処理
                    ss_counter += 1
                    path = screenshot_dir / self._screenshot_filename(
                        index, tc.name, ss_counter, action.timing
                    )
                    try:
                        if action.scroll:
                            take_scroll_screenshot(driver, path)
                        else:
                            take_screenshot(driver, path)
                        result.screenshot_paths.append(path)
                        self._logger.info(f"  スクリーンショット保存: {path.name}")
                    except ScreenshotError as e:
                        self._logger.warning(f"  スクリーンショット失敗（テスト継続）: {e}")
                    if action.wait:
                        time.sleep(action.wait)
                else:
                    detail = getattr(action, "selector", getattr(action, "target", ""))
                    self._logger.debug(
                        f"  アクション: {action.type}"
                        + (f" → {detail}" if detail else "")
                    )
                    try:
                        execute_action(driver, action, ctx)
                    except ActionError as e:
                        self._logger.error(f"  アクション失敗: {e}")
                        result.passed = False
                        result.error = str(e)
                        self._take_error_screenshot(driver, tc, index, screenshot_dir, result)
                        return result

            # 後方互換: アクション内に type:screenshot がない場合の screenshot/screenshot_scroll
            if (tc.screenshot or tc.screenshot_scroll) and ss_counter == 0:
                path = screenshot_dir / self._screenshot_filename(index, tc.name)
                try:
                    if tc.screenshot_scroll:
                        take_scroll_screenshot(driver, path)
                    else:
                        take_screenshot(driver, path)
                    result.screenshot_paths.append(path)
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
            result.screenshot_paths.append(error_path)
            self._logger.info(f"  エラー時スクリーンショット保存: {error_path.name}")
        except ScreenshotError as e:
            self._logger.warning(f"  エラー時スクリーンショット失敗: {e}")

    def _screenshot_filename(
        self,
        index: int,
        name: str,
        ss_index: Optional[int] = None,
        timing: Optional[str] = None,
        error: bool = False,
    ) -> str:
        safe_name = re.sub(r"[^\w]", "_", name)
        suffix = "_ERROR" if error else ""

        if ss_index is not None:
            # 新スタイル: type:screenshot アクション使用時
            safe_timing = re.sub(r"[^\w]", "_", timing) if timing else ""
            timing_part = f"_{safe_timing}" if safe_timing else ""
            return f"{index:03d}_{safe_name}_{ss_index:02d}{timing_part}{suffix}.jpg"
        else:
            # 後方互換スタイル: screenshot: true 使用時
            return f"{index:03d}_{safe_name}{suffix}.jpg"
