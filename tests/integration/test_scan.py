from pathlib import Path
import shutil
import subprocess
import pytest
from vfg.scan import scan_binary
from vfg.errors import VFGError

ELF=Path("runs/mechanism/probe.elf")
@pytest.mark.rvv
def test_real_elf_maps_both_policies(tmp_path):
    if not ELF.exists(): pytest.skip("run scripts/rvv_probe.py")
    result=scan_binary(ELF)
    assert {s["mnemonic"] for s in result["sites"]}=={"vfredosum.vs","vfredusum.vs"}
    assert all(s["source_candidates"] for s in result["sites"])
    assert any("ordered" in s["symbols"] for s in result["sites"])
    stripped=tmp_path/"stripped.elf";shutil.copy(ELF,stripped)
    subprocess.run(["llvm-strip","--strip-debug",str(stripped)],check=True)
    result2=scan_binary(stripped)
    assert result2["site_count"]==2
    assert all(not s["source_candidates"] for s in result2["sites"])
    assert result2["sites"][0]["site_id"]!=result["sites"][0]["site_id"]

def test_invalid_elf(tmp_path):
    p=tmp_path/"bad";p.write_bytes(b"not an ELF")
    with pytest.raises(VFGError): scan_binary(p)

def test_native_binary_is_not_rvv():
    p=Path("build/host-release/runner/vfg-llama-runner")
    if not p.exists(): pytest.skip("native runner not built")
    import platform
    if platform.system()=="Darwin": assert scan_binary(p)["status"]=="not_applicable"

