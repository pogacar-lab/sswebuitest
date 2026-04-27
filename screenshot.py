from __future__ import annotations

import io
import time
from pathlib import Path

from PIL import Image

from driver_protocol import DriverProtocol
from logger import get_logger


class ScreenshotError(Exception):
    pass


def take_screenshot(driver: DriverProtocol, output_path: Path, quality: int = 90) -> None:
    try:
        png_bytes = driver.get_screenshot_png()
        _save_as_jpeg(png_bytes, output_path, quality)
        get_logger().debug(f"スクリーンショット保存: {output_path}")
    except Exception as e:
        raise ScreenshotError(f"スクリーンショットの保存に失敗しました: {e}") from e


def take_scroll_screenshot(
    driver: DriverProtocol,
    output_path: Path,
    scroll_pause: float = 0.3,
    quality: int = 90,
) -> None:
    try:
        total_height = driver.execute_js("return document.body.scrollHeight")
        viewport_height = driver.execute_js("return window.innerHeight")

        if total_height <= viewport_height:
            take_screenshot(driver, output_path, quality)
            return

        driver.execute_js("window.scrollTo(0, 0)")
        time.sleep(scroll_pause)

        strips: list[bytes] = []
        scroll_y = 0

        while scroll_y < total_height:
            strips.append(driver.get_screenshot_png())
            scroll_y += viewport_height
            driver.execute_js(f"window.scrollTo(0, {scroll_y})")
            time.sleep(scroll_pause)

        image = _stitch_images(strips, total_height, viewport_height)
        image.save(output_path, "JPEG", quality=quality)
        get_logger().debug(f"スクロールスクリーンショット保存: {output_path} (高さ: {total_height}px)")
    except ScreenshotError:
        raise
    except Exception as e:
        raise ScreenshotError(f"スクロールスクリーンショットの保存に失敗しました: {e}") from e


def _stitch_images(strips: list[bytes], total_height: int, viewport_height: int) -> Image.Image:
    pil_strips = [Image.open(io.BytesIO(s)).convert("RGB") for s in strips]
    width = pil_strips[0].width
    canvas = Image.new("RGB", (width, total_height))

    y_offset = 0
    for i, img in enumerate(pil_strips):
        if i < len(pil_strips) - 1:
            canvas.paste(img, (0, y_offset))
            y_offset += viewport_height
        else:
            remaining = total_height - y_offset
            if remaining > 0:
                cropped = img.crop((0, img.height - remaining, img.width, img.height))
                canvas.paste(cropped, (0, y_offset))

    return canvas


def _save_as_jpeg(png_bytes: bytes, output_path: Path, quality: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    image.save(output_path, "JPEG", quality=quality)
