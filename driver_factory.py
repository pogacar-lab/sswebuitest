from __future__ import annotations

from schema import Environment
from driver_protocol import DriverProtocol


def create_driver(env: Environment) -> DriverProtocol:
    """環境設定の engine フィールドに応じて適切なドライバーを返す。"""
    if env.engine == "playwright":
        from playwright_driver import PlaywrightDriver
        return PlaywrightDriver(env)

    from selenium_driver import SeleniumDriver
    return SeleniumDriver(env)
