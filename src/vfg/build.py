"""Build a locked source snapshot and record actual compiler/artifact identities."""

from pathlib import Path
import os
import shutil
import subprocess
import tarfile
import hashlib
from .errors import VFGError
from .manifest import atomic_json, digest, file_digest, load_document, now
from .schema import Stack
from .assets import native_root

ROOT = native_root()


def find_tool(name):
    """A tool on PATH, or one installed next to this Python (the `ninja` PyPI package)."""
    import sys

    path = shutil.which(name)
    if path is None:
        candidate = Path(sys.executable).parent / name
        path = str(candidate) if candidate.is_file() else None
    if path is None:
        raise VFGError(f"{name} not found; install it or run `pip install {name}`")
    return path


def apply_snapshot_patch(root):
    path = root / "third_party/llama.cpp/ggml/CMakeLists.txt"
    text = path.read_text()
    old = "if(GIT_EXE)\n"
    new = "if(GIT_EXE AND NOT DEFINED VFG_SOURCE_SNAPSHOT)\n"
    if new not in text:
        if text.count(old) != 1:
            raise VFGError("snapshot patch does not match pinned source")
        path.write_text(text.replace(old, new, 1))


def build_native(
    build_dir,
    stack_path=None,
    root=ROOT,
    compiler=None,
    extra_flags=None,
    candidate_flags=None,
    strict_sources=None,
    reduction_policy="native",
):
    root = Path(root).resolve()
    extra_flags = list(extra_flags or [])
    candidate_flags = list(candidate_flags or [])
    strict_sources = list(strict_sources or [])
    if candidate_flags or strict_sources:
        if not candidate_flags or not strict_sources:
            raise VFGError("selective builds need both candidate flags and strict sources")
        if extra_flags:
            raise VFGError("selective builds use the launcher, not global extra flags")
    build_dir = Path(build_dir).resolve()
    lock = load_document(root / "third_party/llama.lock.json")
    if not (root / "third_party/llama.cpp/include/llama.h").is_file():
        raise VFGError("source snapshot missing; run scripts/bootstrap.py")
    archive = root / "third_party/llama.tar.gz"
    if not archive.exists() or file_digest(archive) != lock["archive_sha256"]:
        raise VFGError("source archive identity mismatch; run bootstrap")
    checked = 0
    with tarfile.open(archive) as tf:
        for member in tf:
            if not member.isfile():
                continue
            relative = Path(*Path(member.name).parts[1:])
            source = root / "third_party/llama.cpp" / relative
            expected = tf.extractfile(member).read()
            actual = source.read_bytes()
            if str(relative) == "ggml/CMakeLists.txt":
                actual = actual.replace(
                    b"if(GIT_EXE AND NOT DEFINED VFG_SOURCE_SNAPSHOT)\n", b"if(GIT_EXE)\n", 1
                )
            if hashlib.sha256(actual).digest() != hashlib.sha256(expected).digest():
                raise VFGError(f"downloaded source modified: {relative}")
            checked += 1
    apply_snapshot_patch(root)
    manifest = build_runner(
        build_dir,
        root / "third_party/llama.cpp",
        lock["revision"],
        root=root,
        compiler=compiler,
        extra_flags=extra_flags,
        candidate_flags=candidate_flags,
        strict_sources=strict_sources,
        reduction_policy=reduction_policy,
    )
    manifest["verified_upstream_files"] = checked
    atomic_json(build_dir / "build-manifest.json", manifest)
    binary = build_dir / "runner/vfg-llama-runner"
    compiler = manifest["compiler"]
    source_hash = manifest["source_digest"]
    if stack_path:
        stack_path = Path(stack_path).resolve()
        stack = Stack(
            id="baseline" if reduction_policy == "native" else reduction_policy,
            source_revision=lock["revision"],
            source_digest=source_hash,
            binary=os.path.relpath(binary, stack_path.parent),
            binary_sha256=file_digest(binary),
            compiler=compiler,
            flags=["-O2", "-g", "-fno-fast-math", "-ffp-contract=off"]
            + extra_flags
            + candidate_flags,
            reduction_policy=reduction_policy,
            build_manifest=os.path.relpath(build_dir / "build-manifest.json", stack_path.parent),
            build_manifest_sha256=file_digest(build_dir / "build-manifest.json"),
        )
        atomic_json(stack_path, stack.model_dump())
    return manifest


def c_compiler_name(cxx):
    """The C compiler that belongs to a C++ compiler name: clang++-18 -> clang-18, g++-16 -> gcc-16."""
    for cpp, c in (("clang++", "clang"), ("g++", "gcc"), ("c++", "cc")):
        if cxx.startswith(cpp) or cxx.endswith(cpp) or cpp + "-" in cxx:
            return cxx.replace(cpp, c, 1)
    return "clang" if "clang" in cxx else "gcc"


def build_runner(
    build_dir,
    llama_dir,
    revision,
    root=ROOT,
    compiler=None,
    extra_flags=None,
    candidate_flags=None,
    strict_sources=None,
    reduction_policy="native",
    cmake_args=None,
    llama_source=None,
):
    """Configure and build the runner against one llama.cpp tree; write build-manifest.json."""
    root = Path(root).resolve()
    build_dir = Path(build_dir).resolve()
    llama_dir = Path(llama_dir).resolve()
    extra_flags = list(extra_flags or [])
    candidate_flags = list(candidate_flags or [])
    strict_sources = list(strict_sources or [])
    cmake_args = list(cmake_args or [])
    if any(not a.startswith("-D") for a in cmake_args):
        raise VFGError("CMake arguments must have the form -DNAME=VALUE")
    build_dir.mkdir(parents=True, exist_ok=True)
    ninja = find_tool("ninja")
    configure = [
        find_tool("cmake"),
        "-S",
        str(root),
        "-B",
        str(build_dir),
        "-G",
        "Ninja",
        f"-DCMAKE_MAKE_PROGRAM={ninja}",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DVFG_BUILD_RUNNER=ON",
        f"-DVFG_LLAMA_DIR={llama_dir}",
        f"-DVFG_LLAMA_COMMIT={revision}",
        *cmake_args,
    ]
    if llama_source is not None:
        # Fetched trees may sit inside another git repository; never embed its HEAD.
        configure.append("-DVFG_FETCHED_TREE=ON")
    if compiler is not None:
        compiler = Path(compiler).absolute()
        c_compiler = compiler.with_name(c_compiler_name(compiler.name))
        configure.extend([f"-DCMAKE_CXX_COMPILER={compiler}", f"-DCMAKE_C_COMPILER={c_compiler}"])
    if extra_flags:
        configure.append("-DVFG_EXTRA_FLAGS=" + " ".join(extra_flags))
    launcher_info = None
    if candidate_flags or strict_sources:
        launcher = root / "scripts/flag_filter.py"
        config_path = build_dir / "flag-filter.json"
        atomic_json(
            config_path,
            {
                "candidate_flags": candidate_flags,
                "strict_flags": ["-fno-fast-math", "-ffp-contract=off"],
                "strict_sources": strict_sources,
            },
        )
        launcher_info = {
            "path": str(launcher),
            "sha256": file_digest(launcher),
            "config": load_document(config_path),
            "config_sha256": file_digest(config_path),
        }
        configure.extend(
            [
                f"-DCMAKE_C_COMPILER_LAUNCHER={launcher};{config_path}",
                f"-DCMAKE_CXX_COMPILER_LAUNCHER={launcher};{config_path}",
            ]
        )
    build = [configure[0], "--build", str(build_dir), "-j", str(os.cpu_count() or 4)]
    for name, command in (("configure", configure), ("build", build)):
        p = subprocess.run(command, text=True, capture_output=True)
        (build_dir / f"{name}.log").write_text(p.stdout + p.stderr)
        if p.returncode:
            raise VFGError(f"{name} failed; see {build_dir / name}.log")
        if name == "configure" and "Manually-specified variables were not used" in p.stderr:
            raise VFGError("unused CMake settings")
    binary = build_dir / "runner/vfg-llama-runner"
    cache = (build_dir / "CMakeCache.txt").read_text().splitlines()
    cc = next(
        line.split("=", 1)[1]
        for line in cache
        if line.startswith("CMAKE_CXX_COMPILER:")
    )
    compiler = {
        "path": cc,
        "version": subprocess.check_output([cc, "--version"], text=True).strip(),
        "sha256": file_digest(Path(cc).resolve()),
    }
    source_files = {}
    for directory in ("runner", "microbench", "third_party/patches"):
        for p in sorted((root / directory).rglob("*")):
            if p.is_file():
                source_files[p.relative_to(root).as_posix()] = file_digest(p)
    for name in ("CMakeLists.txt", "CMakePresets.json", "third_party/llama.lock.json"):
        source_files[name] = file_digest(root / name)
    if llama_source is not None:
        source_files["llama.cpp"] = digest(llama_source)
    source_hash = digest(source_files)
    commands = build_dir / "compile_commands.json"
    manifest = {
        "schema_version": 1,
        "built_at": now(),
        "source_revision": revision,
        "llama_dir": str(llama_dir),
        "llama_source": llama_source,
        "cmake_args": cmake_args,
        "source_files": source_files,
        "source_digest": source_hash,
        "compiler": compiler,
        "extra_flags": extra_flags,
        "launcher": launcher_info,
        "reduction_policy": reduction_policy,
        "configure_command": configure,
        "build_command": build,
        "binary_sha256": file_digest(binary),
        "compile_commands_sha256": file_digest(commands),
        "effective_compile_commands": load_document(commands),
        "effective_build_commands": subprocess.check_output(
            [ninja, "-C", str(build_dir), "-t", "commands", "vfg-llama-runner"], text=True
        ),
        "cmake_cache_sha256": file_digest(build_dir / "CMakeCache.txt"),
        "source_patch_sha256": file_digest(root / "third_party/patches/0001-snapshot-version.patch"),
    }
    if shutil.which("otool"):
        manifest["dynamic_libraries"] = subprocess.check_output(["otool", "-L", str(binary)], text=True)
    atomic_json(build_dir / "build-manifest.json", manifest)
    return manifest
