from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select as SeleniumSelect
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager

from schema import BrowserType, Environment
from driver_protocol import BrowserStartError
from logger import get_logger

# この環境変数が設定されているとオフラインモードで動作する
DRIVER_DIR_ENV = "WEBUITEST_DRIVER_DIR"

_DRIVER_FILENAMES: dict[BrowserType, tuple[str, str]] = {
    BrowserType.CHROME:  ("chromedriver.exe",  "chromedriver"),
    BrowserType.FIREFOX: ("geckodriver.exe",   "geckodriver"),
    BrowserType.EDGE:    ("msedgedriver.exe",  "msedgedriver"),
}


def _resolve_driver_executable(browser: BrowserType) -> Optional[str]:
    """環境変数 WEBUITEST_DRIVER_DIR が設定されていればオフラインドライバーのパスを返す。
    未設定の場合は None を返し、webdriver-manager によるオンライン取得に委ねる。
    """
    driver_dir = os.environ.get(DRIVER_DIR_ENV)
    if not driver_dir:
        return None

    dir_path = Path(driver_dir)
    win_name, other_name = _DRIVER_FILENAMES[browser]
    exe_name = win_name if os.name == "nt" else other_name
    exe_path = dir_path / exe_name

    if not exe_path.exists():
        raise BrowserStartError(
            f"オフラインドライバーが見つかりません: {exe_path}\n"
            f"  環境変数 {DRIVER_DIR_ENV}={driver_dir}\n"
            f"  {exe_name} を上記ディレクトリに配置してください。"
        )

    get_logger().info(f"オフラインモード: ドライバー = {exe_path}")
    return str(exe_path)


def _resolve_by(selector: str) -> tuple[str, str]:
    if selector.startswith("/") or selector.startswith("("):
        return By.XPATH, selector
    return By.CSS_SELECTOR, selector


class SeleniumDriver:
    """Selenium WebDriver を DriverProtocol に適合させるアダプター。"""

    def __init__(self, env: Environment) -> None:
        self._env = env
        self._driver: Optional[WebDriver] = None

    def start(self) -> SeleniumDriver:
        try:
            self._driver = self._create_driver()
        except Exception as e:
            raise BrowserStartError(f"ブラウザの起動に失敗しました: {e}") from e

        self._driver.set_window_size(self._env.window_width, self._env.window_height)

        if self._env.options.zoom != 1.0:
            self._driver.execute_script(
                f"document.body.style.zoom='{self._env.options.zoom}'"
            )

        get_logger().info(
            f"ブラウザ起動 (Selenium): {self._env.browser.value} "
            f"{self._env.window_width}x{self._env.window_height} "
            f"headless={self._env.options.headless}"
        )
        return self

    def _create_driver(self) -> WebDriver:
        opts = self._env.options
        browser = self._env.browser
        exe = _resolve_driver_executable(browser)  # None = オンライン

        if browser == BrowserType.CHROME:
            options = ChromeOptions()
            if opts.headless:
                options.add_argument("--headless=new")
            if opts.compatibility_mode:
                options.add_argument("--disable-web-security")
                options.add_argument("--allow-running-insecure-content")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            service = ChromeService(exe or ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=options)

        elif browser == BrowserType.FIREFOX:
            options = FirefoxOptions()
            if opts.headless:
                options.add_argument("--headless")
            service = FirefoxService(exe or GeckoDriverManager().install())
            return webdriver.Firefox(service=service, options=options)

        elif browser == BrowserType.EDGE:
            options = EdgeOptions()
            if opts.headless:
                options.add_argument("--headless=new")
            if opts.compatibility_mode:
                options.add_argument("--disable-web-security")
            service = EdgeService(exe or EdgeChromiumDriverManager().install())
            return webdriver.Edge(service=service, options=options)

        raise BrowserStartError(f"Selenium では未対応のブラウザです: {browser.value}")

    # ---- DriverProtocol 実装 ----

    def navigate(self, url: str) -> None:
        self._driver.get(url)

    def do_click(self, selector: str, timeout: float) -> None:
        by, sel = _resolve_by(selector)
        WebDriverWait(self._driver, timeout).until(
            EC.element_to_be_clickable((by, sel))
        ).click()

    def do_fill(self, selector: str, value: str, timeout: float) -> None:
        by, sel = _resolve_by(selector)
        element = WebDriverWait(self._driver, timeout).until(
            EC.visibility_of_element_located((by, sel))
        )
        element.clear()
        element.send_keys(value)

    def do_select(self, selector: str, value: str, timeout: float) -> None:
        by, sel = _resolve_by(selector)
        element = WebDriverWait(self._driver, timeout).until(
            EC.presence_of_element_located((by, sel))
        )
        select = SeleniumSelect(element)
        try:
            select.select_by_value(value)
        except Exception:
            select.select_by_visible_text(value)

    def do_check(self, selector: str, checked: bool, timeout: float) -> None:
        by, sel = _resolve_by(selector)
        element = WebDriverWait(self._driver, timeout).until(
            EC.presence_of_element_located((by, sel))
        )
        if element.is_selected() != checked:
            element.click()

    def get_screenshot_png(self) -> bytes:
        return self._driver.get_screenshot_as_png()

    def execute_js(self, script: str) -> Any:
        return self._driver.execute_script(script)

    def get_window_handles(self) -> list[str]:
        return list(self._driver.window_handles)

    def get_current_window_handle(self) -> str:
        return self._driver.current_window_handle

    def switch_to_window(self, handle: str) -> None:
        self._driver.switch_to.window(handle)

    def close_current_window(self) -> None:
        self._driver.close()

    def wait_for_new_window(self, known_handles: set[str], timeout: float) -> str:
        try:
            WebDriverWait(self._driver, timeout).until(
                lambda d: len(set(d.window_handles) - known_handles) > 0
            )
        except TimeoutException:
            raise TimeoutError(f"新しいウィンドウが {timeout} 秒以内に開きませんでした")
        new_handles = set(self._driver.window_handles) - known_handles
        return new_handles.pop()

    def quit(self) -> None:
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

    def __enter__(self) -> SeleniumDriver:
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.quit()
