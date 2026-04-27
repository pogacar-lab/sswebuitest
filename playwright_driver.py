from __future__ import annotations

import time
import uuid
from typing import Any, Optional

from schema import BrowserType, Environment
from driver_protocol import BrowserStartError
from logger import get_logger


class PlaywrightDriver:
    """Playwright を DriverProtocol に適合させるアダプター。"""

    def __init__(self, env: Environment) -> None:
        self._env = env
        self._playwright_cm: Any = None
        self._pw: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._current_page: Any = None
        self._page_handles: dict[str, Any] = {}   # handle_id -> Page
        self._current_handle: Optional[str] = None

    def start(self) -> PlaywrightDriver:
        try:
            from playwright.sync_api import sync_playwright

            self._playwright_cm = sync_playwright()
            self._pw = self._playwright_cm.__enter__()

            opts = self._env.options
            browser_type = self._env.browser

            launch_kwargs: dict[str, Any] = {"headless": opts.headless}
            if opts.compatibility_mode:
                launch_kwargs["args"] = ["--disable-web-security"]

            if browser_type == BrowserType.CHROMIUM:
                self._browser = self._pw.chromium.launch(**launch_kwargs)
            elif browser_type == BrowserType.CHROME:
                self._browser = self._pw.chromium.launch(channel="chrome", **launch_kwargs)
            elif browser_type == BrowserType.EDGE:
                self._browser = self._pw.chromium.launch(channel="msedge", **launch_kwargs)
            elif browser_type == BrowserType.FIREFOX:
                self._browser = self._pw.firefox.launch(**launch_kwargs)
            elif browser_type == BrowserType.WEBKIT:
                self._browser = self._pw.webkit.launch(**launch_kwargs)
            else:
                raise BrowserStartError(f"Playwright では未対応のブラウザです: {browser_type.value}")

            context_kwargs: dict[str, Any] = {
                "viewport": {
                    "width": self._env.window_width,
                    "height": self._env.window_height,
                },
            }
            if opts.compatibility_mode:
                context_kwargs["bypass_csp"] = True

            self._context = self._browser.new_context(**context_kwargs)

            if opts.zoom != 1.0:
                # 各ページ読み込み前に zoom を注入
                self._context.add_init_script(
                    f"Object.defineProperty(document.documentElement.style, 'zoom', "
                    f"{{ value: '{opts.zoom}', writable: true }});"
                    f"document.documentElement.style.zoom = '{opts.zoom}';"
                )

            page = self._context.new_page()
            handle_id = str(uuid.uuid4())
            self._page_handles[handle_id] = page
            self._current_handle = handle_id
            self._current_page = page

        except BrowserStartError:
            raise
        except Exception as e:
            raise BrowserStartError(f"ブラウザの起動に失敗しました: {e}") from e

        get_logger().info(
            f"ブラウザ起動 (Playwright): {self._env.browser.value} "
            f"{self._env.window_width}x{self._env.window_height} "
            f"headless={self._env.options.headless}"
        )
        return self

    def _page(self) -> Any:
        return self._current_page

    def _locator(self, selector: str) -> Any:
        if selector.startswith("/") or selector.startswith("("):
            return self._page().locator(f"xpath={selector}")
        return self._page().locator(selector)

    # ---- DriverProtocol 実装 ----

    def navigate(self, url: str) -> None:
        self._page().goto(url)

    def do_click(self, selector: str, timeout: float) -> None:
        self._locator(selector).click(timeout=timeout * 1000)

    def do_fill(self, selector: str, value: str, timeout: float) -> None:
        loc = self._locator(selector)
        loc.wait_for(state="visible", timeout=timeout * 1000)
        loc.fill(value, timeout=timeout * 1000)

    def do_select(self, selector: str, value: str, timeout: float) -> None:
        loc = self._locator(selector)
        loc.wait_for(state="visible", timeout=timeout * 1000)
        try:
            loc.select_option(value=value, timeout=timeout * 1000)
        except Exception:
            loc.select_option(label=value, timeout=timeout * 1000)

    def do_check(self, selector: str, checked: bool, timeout: float) -> None:
        loc = self._locator(selector)
        loc.wait_for(state="visible", timeout=timeout * 1000)
        if checked:
            loc.check(timeout=timeout * 1000)
        else:
            loc.uncheck(timeout=timeout * 1000)

    def get_screenshot_png(self) -> bytes:
        return self._page().screenshot()

    def execute_js(self, script: str) -> Any:
        # Playwright の evaluate() は "return " プレフィックス不要
        clean = script.strip()
        if clean.startswith("return "):
            clean = clean[7:]
        return self._page().evaluate(clean)

    def get_window_handles(self) -> list[str]:
        self._sync_new_pages()
        return list(self._page_handles.keys())

    def get_current_window_handle(self) -> str:
        return self._current_handle

    def switch_to_window(self, handle: str) -> None:
        if handle not in self._page_handles:
            raise RuntimeError(f"ウィンドウハンドル '{handle}' が見つかりません")
        self._current_handle = handle
        self._current_page = self._page_handles[handle]
        self._current_page.bring_to_front()

    def close_current_window(self) -> None:
        page = self._current_page
        del self._page_handles[self._current_handle]
        self._current_handle = None
        self._current_page = None
        page.close()

    def wait_for_new_window(self, known_handles: set[str], timeout: float) -> str:
        known_pages = {
            self._page_handles[h] for h in known_handles if h in self._page_handles
        }
        deadline = time.time() + timeout
        while time.time() < deadline:
            for page in self._context.pages:
                if page not in known_pages and page not in self._page_handles.values():
                    new_handle = str(uuid.uuid4())
                    self._page_handles[new_handle] = page
                    return new_handle
            time.sleep(0.1)
        raise TimeoutError(f"新しいウィンドウが {timeout} 秒以内に開きませんでした")

    def _sync_new_pages(self) -> None:
        """context.pages に存在するが未登録のページをレジストリへ追加する。"""
        for page in self._context.pages:
            if page not in self._page_handles.values():
                self._page_handles[str(uuid.uuid4())] = page

    def quit(self) -> None:
        try:
            if self._context is not None:
                self._context.close()
            if self._browser is not None:
                self._browser.close()
            if self._playwright_cm is not None:
                self._playwright_cm.__exit__(None, None, None)
        except Exception:
            pass
        finally:
            self._context = None
            self._browser = None
            self._pw = None
            self._playwright_cm = None
            self._current_page = None

    def __enter__(self) -> PlaywrightDriver:
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.quit()
