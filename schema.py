from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field
from enum import Enum


class BrowserType(str, Enum):
    CHROME = "chrome"
    FIREFOX = "firefox"
    EDGE = "edge"


class BrowserOptions(BaseModel):
    headless: bool = False
    zoom: float = 1.0
    compatibility_mode: bool = False


class Environment(BaseModel):
    env_id: str                 # 識別子（例: chrome_1920x1080）
    browser: BrowserType
    version: Optional[str] = None
    window_width: int = 1280
    window_height: int = 800
    options: BrowserOptions = Field(default_factory=BrowserOptions)


class EnvironmentFile(BaseModel):
    environments: list[Environment]


class ActionBase(BaseModel):
    wait: Optional[float] = None


class ClickAction(ActionBase):
    type: Literal["click"]
    selector: str


class InputAction(ActionBase):
    type: Literal["input"]
    selector: str
    value: str


class SelectAction(ActionBase):
    type: Literal["select"]
    selector: str
    value: str


class CheckAction(ActionBase):
    type: Literal["check"]
    selector: str
    checked: bool


Action = Annotated[
    Union[ClickAction, InputAction, SelectAction, CheckAction],
    Field(discriminator="type"),
]


class TestCase(BaseModel):
    name: str
    entry_url: str
    actions: list[Action] = Field(default_factory=list)
    screenshot: bool = False
    screenshot_scroll: bool = False
    wait: Optional[float] = None


class TestScenario(BaseModel):
    app_name: str
    description: str
    scenario_name: str
    continue_on_error: bool = False
    test_cases: list[TestCase] = Field(default_factory=list)
