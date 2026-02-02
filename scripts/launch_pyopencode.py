import sys
import runpy

# debugpy 会把真实参数放在 "--" 之后
if "--" in sys.argv:
    args = sys.argv[sys.argv.index("--") + 1 :]
else:
    args = sys.argv[1:]

# 让 Typer 看到干净的 argv
sys.argv = ["pyopencode"] + args

# 等价于: python -m pyopencode ...
runpy.run_module("pyopencode", run_name="__main__")
