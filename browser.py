from __future__ import annotations

from typing import Optional

from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager

from schema import BrowserType, Environment
from logger import get_logger


class BrowserStartError(Exception):
    pass


class BrowserManager:
    def __init__(self, env: Environment) -> None:
        self._env = env
        self._driver: Optional[WebDriver] = None

    def start(self) -> WebDriver:
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
            f"ブラウザ起動: {self._env.browser.value} "
            f"{self._env.window_width}x{self._env.window_height} "
            f"headless={self._env.options.headless}"
        )
        return self._driver

    def _create_driver(self) -> WebDriver:
        opts = self._env.options
        browser = self._env.browser

        if browser == BrowserType.CHROME:
            options = ChromeOptions()
            if opts.headless:
                options.add_argument("--headless=new")
            if opts.compatibility_mode:
                options.add_argument("--disable-web-security")
                options.add_argument("--allow-running-insecure-content")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            service = ChromeService(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=options)

        elif browser == BrowserType.FIREFOX:
            options = FirefoxOptions()
            if opts.headless:
                options.add_argument("--headless")
            service = FirefoxService(GeckoDriverManager().install())
            return webdriver.Firefox(service=service, options=options)

        elif browser == BrowserType.EDGE:
            options = EdgeOptions()
            if opts.headless:
                options.add_argument("--headless=new")
            if opts.compatibility_mode:
                options.add_argument("--disable-web-security")
            service = EdgeService(EdgeChromiumDriverManager().install())
            return webdriver.Edge(service=service, options=options)

        raise BrowserStartError(f"未対応のブラウザ: {browser}")

    def quit(self) -> None:
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

    def get_driver(self) -> WebDriver:
        if self._driver is None:
            raise RuntimeError("ブラウザが起動していません。start()を先に呼び出してください。")
        return self._driver

    def __enter__(self) -> BrowserManager:
        self.start()
        return self

    def __exit__(self, *args) -> None:
        self.quit()
