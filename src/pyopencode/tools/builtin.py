from __future__ import annotations
from pathlib import Path

from .registry import ToolRegistry
from .base import ToolContext

from .builtin_tools.listdir import ListDirTool
from .builtin_tools.glob_tool import GlobTool
from .builtin_tools.grep_tool import GrepTool
from .builtin_tools.file_read import ReadFileTool
from .builtin_tools.file_write import WriteFileTool
from .builtin_tools.file_edit import EditFileTool
from .builtin_tools.file_multiedit import MultiEditFileTool
from .builtin_tools.patch_tool import PatchTool
from .builtin_tools.bash_tool import BashTool
from .builtin_tools.webfetch_tool import WebFetchTool
from .builtin_tools.todo_tools import TodoReadTool, TodoWriteTool
from .builtin_tools.skill_tool import SkillTool
from .builtin_tools.question_tool import QuestionTool
from .builtin_tools.lsp_tool import LspTool

def register_builtin_tools(registry: ToolRegistry) -> None:
    registry.register(ListDirTool())
    registry.register(GlobTool())
    registry.register(GrepTool())
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(EditFileTool())
    registry.register(MultiEditFileTool())
    registry.register(PatchTool())
    registry.register(BashTool())
    registry.register(WebFetchTool())
    registry.register(TodoReadTool())
    registry.register(TodoWriteTool())
    registry.register(SkillTool())
    registry.register(QuestionTool())
    registry.register(LspTool())
