"""Locate the native build tree and bundled data in a checkout or an installed wheel."""

from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
CHECKOUT = PACKAGE.parents[1]


def native_root():
    """Directory that holds CMakeLists.txt, runner/, microbench/ and third_party/ locks."""
    for root in (CHECKOUT, PACKAGE / "_native"):
        if (root / "CMakeLists.txt").is_file() and (root / "runner/CMakeLists.txt").is_file():
            return root
    raise FileNotFoundError("native build files are missing from this installation")
