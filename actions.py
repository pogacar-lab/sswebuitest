from __future__ import annotations

import time
from typing import Union

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select as SeleniumSelect
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)

from schema import Action, ClickAction, InputAction, SelectAction, CheckAction

DEFAULT_WAIT_TIMEOUT = 10


class ActionError(Exception):
    def __init__(self, action: Action, cause: Exception) -> None:
        self.action = action
        self.cause = cause
        super().__init__(
            f"アクション '{action.type}' セレクタ '{action.selector}' の実行に失敗しました: {cause}"
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


def execute_action(driver: WebDriver, action: Action, timeout: float = DEFAULT_WAIT_TIMEOUT) -> None:
    if isinstance(action, ClickAction):
        execute_click(driver, action, timeout)
    elif isinstance(action, InputAction):
        execute_input(driver, action, timeout)
    elif isinstance(action, SelectAction):
        execute_select(driver, action, timeout)
    elif isinstance(action, CheckAction):
        execute_check(driver, action, timeout)

    if action.wait:
        time.sleep(action.wait)
