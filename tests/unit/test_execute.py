import json
from pathlib import Path
import sys
import pytest
from vfg.execute.local import execute_command
from vfg.errors import VFGError, InsufficientEvidence

def test_arguments_and_environment(tmp_path):
    command=[sys.executable,"-c","import sys; print(repr(sys.argv[1]))","literal $(echo hidden)"]
    r=execute_command(command,tmp_path/"run")
    assert r["status"]=="complete"
    assert "'literal $(echo hidden)'" in (tmp_path/"run/stdout.txt").read_text()
    assert "OMP_NUM_THREADS" in r["environment"]

def test_timeout_and_error(tmp_path):
    r=execute_command([sys.executable,"-c","import time; time.sleep(5)"],tmp_path/"timeout",timeout=.05)
    assert r["status"]=="timeout"
    r=execute_command([sys.executable,"-c","raise SystemExit(7)"],tmp_path/"error")
    assert r["returncode"]==7 and r["status"]=="error"

def test_missing_executable(tmp_path):
    with pytest.raises(VFGError):
        execute_command(["/definitely/not/an/executable"],tmp_path/"missing")

