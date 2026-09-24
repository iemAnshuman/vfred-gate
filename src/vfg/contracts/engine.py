from ..manifest import digest
from ..schema import Verdict


def evaluate_contract(contract, evidence, metrics):
    common = {"contract_sha256": digest(contract.model_dump()), "evidence": evidence, "rules": metrics}
    if evidence.get("errors"):
        return Verdict(verdict="ERROR", exit_code=4, reasons=evidence["errors"], **common)
    if evidence.get("insufficient"):
        return Verdict(verdict="INCONCLUSIVE", exit_code=3, reasons=evidence["insufficient"], **common)
    if len(metrics) != len(contract.rules) or {m["id"] for m in metrics} != {r.id for r in contract.rules}:
        return Verdict(
            verdict="INCONCLUSIVE", exit_code=3, reasons=["not every rule was evaluated"], **common
        )
    failed = [m["id"] for m in metrics if not m["passed"]]
    return Verdict(
        verdict="FAIL" if failed else "PASS",
        exit_code=2 if failed else 0,
        reasons=[f"rule failed: {x}" for x in failed],
        **common,
    )
