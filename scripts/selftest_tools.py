from __future__ import annotations
import tempfile
from pathlib import Path
import subprocess
import textwrap

from pyopencode.tools.builtin_tools.file_write import WriteFileTool
from pyopencode.tools.builtin_tools.file_read import ReadFileTool
from pyopencode.tools.builtin_tools.grep_tool import GrepTool
from pyopencode.tools.builtin_tools.glob_tool import GlobTool
from pyopencode.tools.builtin_tools.listdir import ListDirTool
from pyopencode.tools.builtin_tools.file_edit import EditFileTool
from pyopencode.tools.builtin_tools.patch_tool import PatchTool
from pyopencode.tools.builtin_tools.bash_tool import BashTool
from pyopencode.tools.base import ToolContext

def main():
    with tempfile.TemporaryDirectory() as td:
        cwd = Path(td)
        ctx = ToolContext(cwd=str(cwd))

        # write
        w = WriteFileTool()
        print(w.execute(ctx, {"path":"a.txt","content":"hello\nworld\n"}).content)

        # read
        r = ReadFileTool()
        print("READ:", r.execute(ctx, {"path":"a.txt"}).content.strip())

        # grep
        g = GrepTool()
        print("GREP:", g.execute(ctx, {"pattern":"world","path":"."}).content.strip())

        # glob
        gl = GlobTool()
        print("GLOB:", gl.execute(ctx, {"pattern":"*.txt"}).content.strip())

        # list
        ls = ListDirTool()
        print("LIST:", ls.execute(ctx, {"path":"."}).content.strip())

        # edit (replace line 2)
        e = EditFileTool()
        print(e.execute(ctx, {"path":"a.txt","start_line":2,"end_line":2,"new_text":"WORLD"}).content)
        print("READ2:", r.execute(ctx, {"path":"a.txt"}).content.strip())

        # patch (init git so git apply works)
        subprocess.run(["git","init"], cwd=cwd, check=True, stdout=subprocess.DEVNULL)
        diff = textwrap.dedent("""\
        diff --git a/a.txt b/a.txt
        --- a/a.txt
        +++ b/a.txt
        @@ -1,2 +1,2 @@
        -hello
        -WORLD
        +hello!!!
        +WORLD!!!
        """)
        p = PatchTool()
        print(p.execute(ctx, {"diff": diff}).content)
        print("READ3:", r.execute(ctx, {"path":"a.txt"}).content.strip())

        # bash
        b = BashTool()
        print(b.execute(ctx, {"command":"python -c \"print(1+1)\""}).content)

if __name__ == "__main__":
    main()
