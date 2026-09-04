"""Stable plugin import: nous-plugin/1, nous-pack/2, DeepSeek Harness bundles."""

from app.plugin.github import fetch_plugin_archive, parse_plugin_source
from app.plugin.loader import parse_plugin_directory

__all__ = [
    "fetch_plugin_archive",
    "parse_plugin_directory",
    "parse_plugin_source",
]
