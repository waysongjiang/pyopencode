from __future__ import annotations
import subprocess
from dataclasses import dataclass
from typing import Sequence, Optional

@dataclass
class CmdResult:
    returncode: int
    stdout: str
    stderr: str

def run_cmd(cmd: Sequence[str], cwd: str, timeout: Optional[int]=120) -> CmdResult:
    p = subprocess.run(
        list(cmd),
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        shell=False,
    )
    return CmdResult(p.returncode, p.stdout, p.stderr)
