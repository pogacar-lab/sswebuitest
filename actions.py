from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from driver_protocol import DriverProtocol
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


def execute_click(driver: DriverProtocol, action: ClickAction, timeout: float = DEFAULT_WAIT_TIMEOUT) -> None:
    try:
        driver.do_click(action.selector, timeout)
    except Exception as e:
        raise ActionError(action, e) from e


def execute_input(driver: DriverProtocol, action: InputAction, timeout: float = DEFAULT_WAIT_TIMEOUT) -> None:
    try:
        driver.do_fill(action.selector, action.value, timeout)
    except Exception as e:
        raise ActionError(action, e) from e


def execute_select(driver: DriverProtocol, action: SelectAction, timeout: float = DEFAULT_WAIT_TIMEOUT) -> None:
    try:
        driver.do_select(action.selector, action.value, timeout)
    except Exception as e:
        raise ActionError(action, e) from e


def execute_check(driver: DriverProtocol, action: CheckAction, timeout: float = DEFAULT_WAIT_TIMEOUT) -> None:
    try:
        driver.do_check(action.selector, action.checked, timeout)
    except Exception as e:
        raise ActionError(action, e) from e


def execute_switch_window(
    driver: DriverProtocol,
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

    current_handle = driver.get_current_window_handle()
    current_handles = set(driver.get_window_handles())

    try:
        new_handle = driver.wait_for_new_window(current_handles, timeout)
    except TimeoutError as e:
        raise ActionError(action, e) from e

    ctx.stack.append(current_handle)
    try:
        driver.switch_to_window(new_handle)
    except Exception as e:
        ctx.stack.pop()  # 失敗したのでスタックを元に戻す
        raise ActionError(action, e) from e

    if alias:
        ctx.registry[alias] = new_handle


def execute_close_window(
    driver: DriverProtocol,
    action: CloseWindowAction,
    ctx: WindowContext,
) -> None:
    """現在のウィンドウを閉じ、スタックから戻り先を復元する。
    スタックが空の場合は残存するウィンドウハンドルの末尾へ移動する。
    """
    closed_handle = driver.get_current_window_handle()
    driver.close_current_window()

    ctx.registry = {k: v for k, v in ctx.registry.items() if v != closed_handle}

    restore_handle: Optional[str] = None
    while ctx.stack:
        candidate = ctx.stack.pop()
        if candidate in driver.get_window_handles():
            restore_handle = candidate
            break

    if restore_handle is None and driver.get_window_handles():
        restore_handle = driver.get_window_handles()[-1]

    if restore_handle:
        try:
            driver.switch_to_window(restore_handle)
        except Exception as e:
            raise ActionError(action, e) from e


def execute_action(
    driver: DriverProtocol,
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
