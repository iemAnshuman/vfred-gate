"""Versioned, strict declarations shared by CLI and controller."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Revision = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]

class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    schema_version: Literal[1] = 1

class Injection(Record):
    tensor: str = Field(min_length=1)
    position: int = Field(ge=0)
    element: int = Field(default=0, ge=0)
    delta: float

class Capture(Record):
    mode: Literal["none", "layer", "operator", "all"] = "none"
    match: str = ""
    payloads: bool = False

class Settings(Record):
    context: int = Field(default=512, ge=8, le=65536)
    max_tokens: int = Field(default=32, ge=1, le=1024)
    threads: Literal[1] = 1
    batch: Literal[1] = 1
    microbatch: Literal[1] = 1
    kv_type: Literal["f32"] = "f32"
    timeout_seconds: float = Field(default=120, gt=0)
    capture: Capture = Field(default_factory=Capture)

class ModelLock(Record):
    repository: str
    revision: Revision
    filename: str
    sha256: Digest
    quantisation: Literal["Q8_0"]
    size_bytes: int = Field(gt=0)
    url: str

class Target(Record):
    id: str
    execution_class: Literal["host", "emulator", "hardware"]
    architecture: str
    command_prefix: list[str] = Field(default_factory=list)
    affinity_cpu: int | None = Field(default=None, ge=0)
    require_affinity: bool = False
    description: str = ""

class Stack(Record):
    id: str
    source_revision: Revision
    source_digest: Digest
    binary: str
    binary_sha256: Digest
    compiler: dict[str, str]
    flags: list[str]
    build_manifest: str | None = None
    build_manifest_sha256: Digest | None = None
    build_class: Literal["diagnostic", "production"] = "diagnostic"
    reduction_policy: str = "native"
    injection: Injection | None = None
    @model_validator(mode="after")
    def injection_is_diagnostic(self):
        if self.injection is not None and self.build_class != "diagnostic":
            raise ValueError("injection requires a diagnostic build")
        if (self.build_manifest is None) != (self.build_manifest_sha256 is None):
            raise ValueError("build manifest path and hash are required together")
        return self

class EvidenceRequirements(Record):
    repetitions: int = Field(default=5, ge=1)
    minimum_cases: int = Field(default=16, ge=1)
    stability: Literal["bitwise_within_stack"] = "bitwise_within_stack"
    require_all_cases: Literal[True] = True
    unexpected_manifest_differences: Literal["reject"] = "reject"

MetricName = Literal["bit_equal_rate", "max_absolute_error", "max_relative_error",
                     "max_ulp_error", "argmax_agreement_rate", "topk_jaccard",
                     "sequence_exact_match_rate"]
class Rule(Record):
    id: str
    metric: MetricName
    alignment: Literal["free_run", "teacher_forced_baseline"] = "free_run"
    operator: Literal["ge", "le"]
    threshold: float
    k: int = Field(default=5, ge=1)
    epsilon: float = Field(default=1e-12, gt=0)
    @model_validator(mode="after")
    def metric_scope(self):
        if self.metric == "sequence_exact_match_rate" and self.alignment != "free_run":
            raise ValueError("sequence metrics require free-running output")
        if self.metric.endswith("_rate") or self.metric == "topk_jaccard":
            if not 0 <= self.threshold <= 1:
                raise ValueError("proportion threshold must be within [0,1]")
        elif self.threshold < 0:
            raise ValueError("error threshold must be nonnegative")
        return self

class Contract(Record):
    id: str
    compatibility_level: Literal["bit", "numeric", "decision", "sequence"]
    rules: list[Rule] = Field(min_length=1)
    evidence: EvidenceRequirements = Field(default_factory=EvidenceRequirements)
    on_insufficient_evidence: Literal["INCONCLUSIVE"] = "INCONCLUSIVE"
    @model_validator(mode="after")
    def unique_ids(self):
        if len({r.id for r in self.rules}) != len(self.rules):
            raise ValueError("duplicate rule ID")
        return self

class Plan(Record):
    id: str
    model: str
    corpus: str
    contract: str
    baseline: str
    candidate: str
    target: str
    cases: list[str] | None = None
    allowed_stack_differences: list[str] = Field(default_factory=list)
    settings: Settings = Field(default_factory=Settings)
    @model_validator(mode="after")
    def unique_cases(self):
        if self.cases is not None and (not self.cases or len(set(self.cases)) != len(self.cases)):
            raise ValueError("cases must be nonempty and unique")
        protected={"source_revision", "source_digest", "build_class", "injection", "reduction_policy",
                   "binary", "binary_sha256", "compiler", "flags", "build_manifest", "build_manifest_sha256"}
        if any(x not in protected for x in self.allowed_stack_differences):
            raise ValueError("unknown allowed stack difference")
        return self

class CorpusCase(Record):
    id: str
    group_id: str
    category: str
    split: Literal["exploratory", "holdout"]
    tokens: list[int] = Field(min_length=1, max_length=128)
    model_sha256: Digest
    tokenizer_sha256: Digest
    formatted_text_sha256: Digest
    @model_validator(mode="after")
    def tokens_nonnegative(self):
        if any(t < 0 for t in self.tokens):
            raise ValueError("negative token ID")
        return self

class Verdict(Record):
    verdict: Literal["PASS", "FAIL", "INCONCLUSIVE", "ERROR"]
    exit_code: Literal[0, 2, 3, 4]
    contract_sha256: Digest | None = None
    legality_status: Literal["not_assessed"] = "not_assessed"
    reasons: list[str] = Field(default_factory=list)
    rules: list[dict] = Field(default_factory=list)
    evidence: dict = Field(default_factory=dict)
    @model_validator(mode="after")
    def consistent_exit(self):
        if self.exit_code != {"PASS":0, "FAIL":2, "INCONCLUSIVE":3, "ERROR":4}[self.verdict]:
            raise ValueError("verdict and exit code disagree")
        return self

SCHEMAS={"stack":Stack, "target":Target, "model":ModelLock, "corpus":CorpusCase,
         "plan":Plan, "contract":Contract, "verdict":Verdict}

