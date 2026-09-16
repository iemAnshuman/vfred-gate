class VFGError(Exception):
    """Configuration, protocol or integrity error (exit 4)."""

class InsufficientEvidence(VFGError):
    """Execution could not supply the required evidence (exit 3)."""

