import pytest

from vfg.errors import VFGError
from vfg.reference import reference_jobs


class Case:
    def __init__(self, id):
        self.id = id


def _jobs(cases, repetitions=2):
    return [
        {"case_id": c.id, "role": "baseline", "mode": mode, "repetition": r,
         "path": f"jobs/c{n:03d}/{mode}/baseline/r{r:03d}"}
        for n, c in enumerate(cases)
        for mode in ("free_run", "teacher_forced_baseline")
        for r in range(repetitions)
    ]


def test_valid_jobs_pass():
    cases = [Case("c000"), Case("c001")]
    assert len(reference_jobs(_jobs(cases), cases, 2)) == 8


def test_duplicate_case_ids_fail():
    cases = [Case("c000"), Case("c000")]
    with pytest.raises(VFGError, match="duplicate case ids"):
        reference_jobs(_jobs(cases), cases, 2)


def test_reused_path_fails():
    cases = [Case("c000")]
    jobs = _jobs(cases)
    jobs[1]["path"] = jobs[0]["path"]  # two repetitions in one directory would fake stability
    with pytest.raises(VFGError, match="unexpected job"):
        reference_jobs(jobs, cases, 2)


def test_missing_first_free_run_fails():
    cases = [Case("c000")]
    jobs = [j for j in _jobs(cases) if not (j["mode"] == "free_run" and j["repetition"] == 0)]
    with pytest.raises(VFGError, match="no free_run r000"):
        reference_jobs(jobs, cases, 2)
