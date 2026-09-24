"""Inventory static RVV reductions and conservative ELF/DWARF mappings."""

from pathlib import Path
import re
import shutil
import subprocess
from elftools.elf.elffile import ELFFile
from elftools.common.exceptions import ELFError
from ..errors import VFGError
from ..manifest import file_digest

ALIASES = {"vfredsum.vs": "vfredusum.vs", "vfwredsum.vs": "vfwredusum.vs"}
REDUCTIONS = {"vfredosum.vs", "vfredusum.vs", "vfwredosum.vs", "vfwredusum.vs"}
INSTRUCTION = re.compile(r"^\s*([0-9a-f]+):\s+([0-9a-f]{4,8})\s+(\S+)\s*(.*)$")


def _lines(elf):
    ranges = []
    if not elf.has_dwarf_info():
        return ranges
    dwarf = elf.get_dwarf_info()
    for cu in dwarf.iter_CUs():
        program = dwarf.line_program_for_CU(cu)
        if program is None:
            continue
        previous = None
        for entry in program.get_entries():
            state = entry.state
            if state is None:
                continue
            if previous is not None and state.address > previous.address:
                try:
                    files = program["file_entry"]
                    item = files[previous.file - 1] if program.header.version < 5 else files[previous.file]
                    name = item.name.decode(errors="replace")
                    directory = item.dir_index
                    dirs = program["include_directory"]
                    if dirs and directory:
                        idx = directory - 1 if program.header.version < 5 else directory
                        if idx < len(dirs):
                            name = str(Path(dirs[idx].decode(errors="replace")) / name)
                    ranges.append((previous.address, state.address, name, previous.line))
                except (IndexError, KeyError, AttributeError):
                    pass
            previous = None if state.end_sequence else state
    return ranges


def scan_binary(binary, output=None, objdump=None):
    binary = Path(binary)
    sha = file_digest(binary)
    with binary.open("rb") as stream:
        magic = stream.read(4)
        stream.seek(0)
        if magic in {b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe"}:
            return {
                "schema_version": 1,
                "binary_sha256": sha,
                "status": "not_applicable",
                "reason": "native Mach-O, not a RISC-V ELF",
                "sites": [],
            }
        try:
            elf = ELFFile(stream)
            if elf["e_machine"] != "EM_RISCV":
                return {
                    "schema_version": 1,
                    "binary_sha256": sha,
                    "status": "not_applicable",
                    "reason": "non-RISC-V ELF",
                    "sites": [],
                }
            if elf.elfclass != 64 or not elf.little_endian:
                raise VFGError("only little-endian RV64 is supported")
            sections = [
                (s.name, s["sh_addr"], s["sh_size"]) for s in elf.iter_sections() if s["sh_flags"] & 4
            ]
            symbols = []
            for section in elf.iter_sections():
                if section["sh_type"] == "SHT_SYMTAB":
                    symbols.extend(
                        (s.name, s["st_value"], s["st_size"])
                        for s in section.iter_symbols()
                        if s["st_info"]["type"] == "STT_FUNC"
                    )
            lines = _lines(elf)
        except ELFError as exc:
            raise VFGError(f"invalid ELF: {exc}") from exc
    objdump = objdump or shutil.which("llvm-objdump")
    if not objdump:
        raise VFGError("llvm-objdump is missing")
    proc = subprocess.run([objdump, "-d", str(binary)], text=True, capture_output=True)
    if proc.returncode:
        raise VFGError(proc.stderr)
    sites = []
    for line in proc.stdout.splitlines():
        match = INSTRUCTION.match(line)
        if not match:
            continue
        address, encoding, mnemonic, operands = match.groups()
        mnemonic = ALIASES.get(mnemonic, mnemonic)
        if mnemonic not in REDUCTIONS:
            continue
        pc = int(address, 16)
        section = next(((n, a) for n, a, size in sections if a <= pc < a + size), None)
        if section is None:
            raise VFGError("instruction outside executable section")
        symbol = [n for n, a, size in symbols if a <= pc < a + size]
        mappings = [{"file": f, "line": line_number} for a, b, f, line_number in lines if a <= pc < b]
        name, base = section
        sites.append(
            {
                "site_id": f"{sha}:{name}:{pc - base:x}",
                "section": name,
                "address": pc,
                "section_offset": pc - base,
                "instruction_bytes": bytes.fromhex(encoding)[::-1].hex(),
                "mnemonic": mnemonic,
                "operands": operands,
                "symbols": symbol,
                "source_candidates": mappings,
                "mapping_status": "source" if mappings else ("symbol" if symbol else "address"),
                "execution_observed": False,
            }
        )
    result = {
        "schema_version": 1,
        "binary_sha256": sha,
        "architecture": "rv64",
        "status": "complete",
        "sites": sites,
        "site_count": len(sites),
        "objdump_version": subprocess.check_output([objdump, "--version"], text=True).splitlines()[0],
    }
    if output:
        from ..manifest import atomic_json

        output = Path(output)
        atomic_json(output, result)
        output.with_suffix(".disassembly.txt").write_text(proc.stdout)
    return result
