"""
Waveshare 7.5" 3-Color (Black/White/Red) E-Paper Display Driver Wrapper.

Provides a clean interface around Waveshare's ``epd7in5b_V2`` library with an
automatic Mock/Simulation mode when running on non-Raspberry Pi hardware or
when SPI hardware is unavailable. In mock mode, ``display()`` composites a
3-color RGB preview PNG so layouts can be inspected on any Linux workstation.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional, Union

from PIL import Image

logger = logging.getLogger(__name__)

EPD_WIDTH = 800
EPD_HEIGHT = 480

# Common fallback locations where Waveshare's e-Paper repo may be cloned on a Pi
_WAVESHARE_FALLBACK_PATHS = (
    Path("/opt/waveshare-epaper/RaspberryPi_JetsonNano/python/lib"),
    Path.home() / "e-Paper" / "RaspberryPi_JetsonNano" / "python" / "lib",
    Path("/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib"),
)


def is_raspberry_pi() -> bool:
    """Return True if running on Raspberry Pi hardware with an active SPI device."""
    model_path = Path("/proc/device-tree/model")
    is_pi_board = False
    if model_path.exists():
        try:
            model_text = model_path.read_text(encoding="utf-8", errors="ignore")
            is_pi_board = "raspberry pi" in model_text.lower()
        except OSError:
            is_pi_board = False

    has_spi = Path("/dev/spidev0.0").exists() or Path("/dev/spidev0.1").exists()
    return is_pi_board and has_spi


def _import_epd7in5b_v2():
    """Import ``waveshare_epd.epd7in5b_V2`` from site-packages or common clone paths."""
    try:
        from waveshare_epd import epd7in5b_V2  # type: ignore[import-not-found]

        return epd7in5b_V2
    except ImportError:
        for candidate in _WAVESHARE_FALLBACK_PATHS:
            if candidate.is_dir() and str(candidate) not in sys.path:
                sys.path.insert(0, str(candidate))
                try:
                    from waveshare_epd import epd7in5b_V2  # type: ignore[import-not-found]

                    logger.debug("Loaded waveshare_epd from fallback path: %s", candidate)
                    return epd7in5b_V2
                except ImportError:
                    continue
        raise


def _prepare_1bit_image(
    image: Image.Image,
    width: int,
    height: int,
    threshold: int = 128,
) -> Image.Image:
    """
    Normalize a PIL Image to 1-bit ('1') mode at the exact panel dimensions.

    On Waveshare 3-color panels, pixel value ``0`` (black) activates ink for that
    channel and ``255`` (white) leaves the pixel uncolored.
    """
    if image.size != (width, height):
        logger.warning(
            "Resizing image from %s to (%d, %d) to match EPD panel dimensions.",
            image.size,
            width,
            height,
        )
        image = image.resize((width, height), Image.Resampling.LANCZOS)

    if image.mode == "1":
        return image

    grayscale = image.convert("L")
    return grayscale.point(lambda px: 255 if px > threshold else 0, mode="1")


def compose_preview_image(
    black_img: Image.Image,
    red_img: Image.Image,
    width: int = EPD_WIDTH,
    height: int = EPD_HEIGHT,
) -> Image.Image:
    """
    Composite 1-bit black and red channel images into a 3-color RGB preview.

    Red ink takes precedence if both channels mark the same pixel as active (0).
    """
    black_1bit = _prepare_1bit_image(black_img, width, height)
    red_1bit = _prepare_1bit_image(red_img, width, height)

    preview = Image.new("RGB", (width, height), (255, 255, 255))
    black_mask = black_1bit.point(lambda px: 255 if px == 0 else 0, mode="L")
    red_mask = red_1bit.point(lambda px: 255 if px == 0 else 0, mode="L")

    preview.paste((15, 15, 15), (0, 0), black_mask)
    preview.paste((205, 32, 32), (0, 0), red_mask)
    return preview


class Waveshare7in5B:
    """
    Wrapper for the Waveshare 7.5-inch 3-Color (B/W/R) V2 E-Paper display.

    Automatically enters Mock/Simulation mode when not running on a Raspberry Pi
    with SPI enabled, or when ``mock=True`` / ``EPAPER_MOCK=1`` is set.
    """

    def __init__(
        self,
        width: int = EPD_WIDTH,
        height: int = EPD_HEIGHT,
        mock: Optional[bool] = None,
        preview_path: Optional[Union[str, Path]] = "data/preview.png",
    ) -> None:
        self.width = width
        self.height = height
        self.preview_path = Path(preview_path) if preview_path else None
        self._epd = None
        self._initialized = False

        env_mock = os.getenv("EPAPER_MOCK", "").strip().lower() in {"1", "true", "yes"}
        if mock is True or env_mock:
            self._mock = True
            logger.info("Waveshare 7.5\" (B) driver initialized in forced MOCK mode.")
        elif mock is False:
            self._epd = self._load_hardware_driver()
            self._mock = False
        else:
            if not is_raspberry_pi():
                self._mock = True
                logger.info(
                    "Raspberry Pi SPI hardware not detected; running Waveshare 7.5\" (B) in MOCK mode."
                )
            else:
                try:
                    self._epd = self._load_hardware_driver()
                    self._mock = False
                    logger.info("Waveshare 7.5\" (B) hardware driver loaded (800x480).")
                except Exception as exc:
                    self._mock = True
                    logger.warning(
                        "Failed to load Waveshare hardware driver (%s); falling back to MOCK mode.",
                        exc,
                    )

    @staticmethod
    def _load_hardware_driver():
        epd_module = _import_epd7in5b_v2()
        return epd_module.EPD()

    @property
    def is_mock(self) -> bool:
        """Return True if the driver is operating in Mock/Simulation mode."""
        return self._mock

    def init(self) -> None:
        """Initialize the e-Paper controller (wakes from deep sleep if needed)."""
        if self._mock:
            logger.debug("[MOCK EPD] init() called (%dx%d)", self.width, self.height)
            self._initialized = True
            return

        assert self._epd is not None
        logger.info("Initializing Waveshare 7.5\" 3-color EPD...")
        self._epd.init()
        self._initialized = True

    def clear(self) -> None:
        """Clear the display to solid white."""
        if not self._initialized:
            self.init()

        if self._mock:
            logger.info("[MOCK EPD] clear() called.")
            if self.preview_path is not None:
                self.preview_path.parent.mkdir(parents=True, exist_ok=True)
                blank = Image.new("RGB", (self.width, self.height), (255, 255, 255))
                blank.save(self.preview_path, format="PNG")
            return

        assert self._epd is not None
        logger.info("Clearing Waveshare 7.5\" 3-color EPD...")
        self._epd.Clear()

    def display(
        self,
        black_img: Image.Image,
        red_img: Image.Image,
        preview_path: Optional[Union[str, Path]] = None,
    ) -> Optional[Path]:
        """
        Render ``black_img`` and ``red_img`` onto the 3-color e-Paper panel.

        In mock mode (or whenever ``preview_path`` is provided), also saves a
        composited 3-color PNG preview.
        """
        if not self._initialized:
            self.init()

        black_1bit = _prepare_1bit_image(black_img, self.width, self.height)
        red_1bit = _prepare_1bit_image(red_img, self.width, self.height)

        target_preview = Path(preview_path) if preview_path else (
            self.preview_path if self._mock else None
        )
        saved_preview: Optional[Path] = None

        if target_preview is not None:
            target_preview.parent.mkdir(parents=True, exist_ok=True)
            composite = compose_preview_image(
                black_1bit, red_1bit, width=self.width, height=self.height
            )
            composite.save(target_preview, format="PNG")
            saved_preview = target_preview
            logger.info("Saved 3-color e-Paper preview to %s", saved_preview)

        if self._mock:
            logger.info("[MOCK EPD] display() completed (preview=%s).", saved_preview)
            return saved_preview

        assert self._epd is not None
        logger.info("Pushing frame buffers to Waveshare 7.5\" 3-color EPD...")
        self._epd.display(
            self._epd.getbuffer(black_1bit),
            self._epd.getbuffer(red_1bit),
        )
        logger.info("EPD refresh complete.")
        return saved_preview

    def sleep(self) -> None:
        """
        Put the e-Paper panel into deep sleep.

        Always call this after ``display()`` to prevent panel degradation and
        minimize power draw.
        """
        if not self._initialized:
            return

        if self._mock:
            logger.debug("[MOCK EPD] sleep() called.")
            self._initialized = False
            return

        assert self._epd is not None
        logger.info("Putting Waveshare 7.5\" EPD into deep sleep.")
        self._epd.sleep()
        self._initialized = False

    def __enter__(self) -> "Waveshare7in5B":
        self.init()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            self.sleep()
        except Exception as exc:
            logger.warning("Error while putting EPD to sleep: %s", exc)
