"""Build a locked source snapshot and record actual compiler/artifact identities."""
from pathlib import Path
import os
import shutil
import subprocess
from .errors import VFGError
from .manifest import atomic_json, digest, file_digest, load_document, now
from .schema import Stack

ROOT=Path(__file__).resolve().parents[2]

def apply_snapshot_patch(root):
    path=root/"third_party/llama.cpp/ggml/CMakeLists.txt"
    text=path.read_text()
    old="if(GIT_EXE)\n";new="if(GIT_EXE AND NOT DEFINED VFG_SOURCE_SNAPSHOT)\n"
    if new not in text:
        if text.count(old)!=1: raise VFGError("snapshot patch does not match pinned source")
        path.write_text(text.replace(old,new,1))

def build_native(build_dir, stack_path=None, root=ROOT):
    root=Path(root).resolve();build_dir=Path(build_dir).resolve()
    lock=load_document(root/"third_party/llama.lock.json")
    if not (root/"third_party/llama.cpp/include/llama.h").is_file():
        raise VFGError("source snapshot missing; run scripts/bootstrap.py")
    apply_snapshot_patch(root)
    build_dir.mkdir(parents=True,exist_ok=True)
    configure=["cmake","-S",str(root),"-B",str(build_dir),"-G","Ninja","-DCMAKE_BUILD_TYPE=Release","-DVFG_BUILD_RUNNER=ON"]
    build=["cmake","--build",str(build_dir),"-j","4"]
    for name,command in (("configure",configure),("build",build)):
        p=subprocess.run(command,text=True,capture_output=True)
        (build_dir/f"{name}.log").write_text(p.stdout+p.stderr)
        if p.returncode: raise VFGError(f"{name} failed; see {build_dir/name}.log")
        if name=="configure" and "Manually-specified variables were not used" in p.stderr:
            raise VFGError("unused CMake settings")
    binary=build_dir/"runner/vfg-llama-runner"
    cc=shutil.which("c++")
    compiler={"path":cc,"version":subprocess.check_output([cc,"--version"],text=True).strip(),
              "sha256":file_digest(Path(cc).resolve())}
    source_files={}
    for directory in ("runner","microbench","third_party/patches"):
        for p in sorted((root/directory).rglob("*")):
            if p.is_file(): source_files[p.relative_to(root).as_posix()]=file_digest(p)
    for name in ("CMakeLists.txt","CMakePresets.json","third_party/llama.lock.json"):
        source_files[name]=file_digest(root/name)
    source_hash=digest(source_files)
    commands=build_dir/"compile_commands.json"
    manifest={"schema_version":1,"built_at":now(),"source_revision":lock["revision"],
              "source_files":source_files,"source_digest":source_hash,"compiler":compiler,
              "configure_command":configure,"build_command":build,"binary_sha256":file_digest(binary),
              "compile_commands_sha256":file_digest(commands),
              "cmake_cache_sha256":file_digest(build_dir/"CMakeCache.txt"),
              "source_patch_sha256":file_digest(root/"third_party/patches/0001-snapshot-version.patch")}
    if shutil.which("otool"):
        manifest["dynamic_libraries"]=subprocess.check_output(["otool","-L",str(binary)],text=True)
    atomic_json(build_dir/"build-manifest.json",manifest)
    if stack_path:
        stack_path=Path(stack_path).resolve()
        stack=Stack(id="baseline",source_revision=lock["revision"],source_digest=source_hash,
                    binary=os.path.relpath(binary,stack_path.parent),binary_sha256=file_digest(binary),
                    compiler=compiler,flags=["-O2","-g","-fno-fast-math","-ffp-contract=off"],
                    build_manifest=os.path.relpath(build_dir/"build-manifest.json",stack_path.parent),
                    build_manifest_sha256=file_digest(build_dir/"build-manifest.json"))
        atomic_json(stack_path,stack.model_dump())
    return manifest

