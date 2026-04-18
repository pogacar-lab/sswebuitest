from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select as SeleniumSelect
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    NoSuchWindowException,
)

from schema import (
    Action,
    ClickAction,
    InputAction,
    SelectAction,
    CheckAction,
    ScreenshotAction,
    SwitchWindowAction,
    CloseWindowAction,
)

DEFAULT_WAIT_TIMEOUT = 10


@dataclass
class WindowContext:
    """ウィンドウ別名とスタックを管理するセッションコンテキスト。
    TestRunner によってセッション全体で1つ生成・共有される。
    """
    registry: dict[str, str] = field(default_factory=dict)  # alias -> handle
    stack: list[str] = field(default_factory=list)          # close_window 復帰用スタック


class ActionError(Exception):
    def __init__(self, action, cause: Exception) -> None:
        self.action = action
        self.cause = cause
        detail = ""
        if hasattr(action, "selector"):
            detail = f" セレクタ '{action.selector}'"
        elif hasattr(action, "target"):
            detail = f" ターゲット '{action.target}'"
        super().__init__(
            f"アクション '{action.type}'{detail} の実行に失敗しました: {cause}"
        )


def _resolve_selector(selector: str) -> tuple[str, str]:
    if selector.startswith("/") or selector.startswith("("):
        return By.XPATH, selector
    return By.CSS_SELECTOR, selector


def execute_click(driver: WebDriver, action: ClickAction, timeout: float = DEFAULT_WAIT_TIMEOUT) -> None:
    by, value = _resolve_selector(action.selector)
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )
        element.click()
    except (TimeoutException, NoSuchElementException, StaleElementReferenceException) as e:
        raise ActionError(action, e) from e


def execute_input(driver: WebDriver, action: InputAction, timeout: float = DEFAULT_WAIT_TIMEOUT) -> None:
    by, value = _resolve_selector(action.selector)
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((by, value))
        )
        element.clear()
        element.send_keys(action.value)
    except (TimeoutException, NoSuchElementException, StaleElementReferenceException) as e:
        raise ActionError(action, e) from e


def execute_select(driver: WebDriver, action: SelectAction, timeout: float = DEFAULT_WAIT_TIMEOUT) -> None:
    by, value = _resolve_selector(action.selector)
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        sel = SeleniumSelect(element)
        try:
            sel.select_by_value(action.value)
        except Exception:
            sel.select_by_visible_text(action.value)
    except (TimeoutException, NoSuchElementException, StaleElementReferenceException) as e:
        raise ActionError(action, e) from e


def execute_check(driver: WebDriver, action: CheckAction, timeout: float = DEFAULT_WAIT_TIMEOUT) -> None:
    by, value = _resolve_selector(action.selector)
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        if element.is_selected() != action.checked:
            element.click()
    except (TimeoutException, NoSuchElementException, StaleElementReferenceException) as e:
        raise ActionError(action, e) from e


def execute_switch_window(
    driver: WebDriver,
    action: SwitchWindowAction,
    ctx: WindowContext,
    timeout: float = DEFAULT_WAIT_TIMEOUT,
) -> None:
    """新しいウィンドウへ切り替える。
    target が "new as <alias>" の場合、新ウィンドウを別名で登録する（上書き可）。
    切り替え前のハンドルを close_window 用スタックへ積む。
    """
    alias: Optional[str] = None
    target_part = action.target.strip()
    if " as " in target_part:
        _, alias = target_part.split(" as ", 1)
        alias = alias.strip()

    current_handle = driver.current_window_handle
    current_handles = set(driver.window_handles)

    # 新ウィンドウが開くまで待機
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: len(set(d.window_handles) - current_handles) > 0
        )
    except TimeoutException as e:
        raise ActionError(
            action,
            TimeoutException(f"新しいウィンドウが {timeout} 秒以内に開きませんでした"),
        ) from e

    new_handles = set(driver.window_handles) - current_handles
    new_handle = new_handles.pop()

    # 現在のハンドルをスタックへ積んでから切り替え
    ctx.stack.append(current_handle)
    try:
        driver.switch_to.window(new_handle)
    except NoSuchWindowException as e:
        ctx.stack.pop()  # 失敗したのでスタックを元に戻す
        raise ActionError(action, e) from e

    # エイリアスを登録（既存の場合は上書き）
    if alias:
        ctx.registry[alias] = new_handle


def execute_close_window(
    driver: WebDriver,
    action: CloseWindowAction,
    ctx: WindowContext,
) -> None:
    """現在のウィンドウを閉じ、スタックから戻り先を復元する。
    スタックが空の場合は残存するウィンドウハンドルの末尾へ移動する。
    """
    closed_handle = driver.current_window_handle
    driver.close()

    # 閉じたハンドルをレジストリから除去
    ctx.registry = {k: v for k, v in ctx.registry.items() if v != closed_handle}

    # スタックから有効な戻り先を取得
    restore_handle: Optional[str] = None
    while ctx.stack:
        candidate = ctx.stack.pop()
        if candidate in driver.window_handles:
            restore_handle = candidate
            break

    if restore_handle is None and driver.window_handles:
        restore_handle = driver.window_handles[-1]

    if restore_handle:
        try:
            driver.switch_to.window(restore_handle)
        except NoSuchWindowException as e:
            raise ActionError(action, e) from e


def execute_action(
    driver: WebDriver,
    action: Action,
    ctx: Optional[WindowContext] = None,
    timeout: float = DEFAULT_WAIT_TIMEOUT,
) -> None:
    """アクションを実行する。
    ScreenshotAction は runner.py 側でインライン処理するため、ここでは無視する。
    switch_window / close_window は WindowContext が必要。
    """
    if isinstance(action, ClickAction):
        execute_click(driver, action, timeout)
    elif isinstance(action, InputAction):
        execute_input(driver, action, timeout)
    elif isinstance(action, SelectAction):
        execute_select(driver, action, timeout)
    elif isinstance(action, CheckAction):
        execute_check(driver, action, timeout)
    elif isinstance(action, SwitchWindowAction):
        execute_switch_window(driver, action, ctx or WindowContext(), timeout)
    elif isinstance(action, CloseWindowAction):
        execute_close_window(driver, action, ctx or WindowContext())
    # ScreenshotAction はここでは処理しない

    if action.wait:
        time.sleep(action.wait)
