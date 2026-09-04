"""Parse an extracted directory as a Nous plugin."""

from __future__ import annotations

from pathlib import Path

from app.plugin.dsh import is_dsh_package, synthesize_dsh_pack
from app.skill.pack_format import ParsedPack, parse_pack_directory


def parse_plugin_directory(pack_root: Path) -> ParsedPack:
    """Accept nous-plugin/1, nous-pack/2, SKILL.md, or a dsh package.json."""
    pack_root = pack_root.resolve()
    has_manifest = (pack_root / "plugin.json").is_file() or (
        pack_root / "pack.json"
    ).is_file()
    has_skill = (pack_root / "SKILL.md").is_file()
    if has_manifest or has_skill:
        return parse_pack_directory(pack_root)
    if is_dsh_package(pack_root):
        return synthesize_dsh_pack(pack_root)
    return parse_pack_directory(pack_root)
