"""日志初始化。"""

from __future__ import annotations

import logging
import sys

_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def setup_logging(debug: bool = False) -> None:
    """配置根日志器；重复调用是幂等的。"""
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(logging.DEBUG if debug else logging.INFO)
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt="%H:%M:%S"))
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if debug else logging.INFO)

    # 第三方库降噪
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)
