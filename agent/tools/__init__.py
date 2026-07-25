"""Tool package. Import `build_registry()` to get a ToolRegistry with all
currently-implemented tools registered."""

from tools.base import ToolRegistry
from tools.file_tools import TOOLS as FILE_TOOLS
from tools.stubs import TOOLS as STUB_TOOLS  # empty for now, see stubs.py
from tools.terminal import TOOLS as TERMINAL_TOOLS


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for tool in [*FILE_TOOLS, *TERMINAL_TOOLS, *STUB_TOOLS]:
        registry.register(tool)
    return registry
