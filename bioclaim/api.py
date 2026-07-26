"""The one-call public API for bioclaim.

    from bioclaim import check
    result = check("TP53 (P04637) is annotated with GO:9999999.")
    print(result.ok, result.problems)

Also a Firewall wrapper to guard any function that returns LLM text.
"""
from dataclasses import dataclass
from typing import List, Optional
from .claims import check_claims, FLAGGED_STATUSES

_LABELS = {
    "NOT_FOUND": "fabricated (does not exist)",
    "INVALID_FORMAT": "malformed identifier",
    "SUPPORTED_LABEL_MISMATCH": "wrong description",
    "SUPPORTED_ENTITY_MISMATCH": "wrong gene/entity",
    "SUPPORTED_OBSOLETE": "obsolete / deprecated",
    "SUPPORTED_FUNCTION_UNSUPPORTED": "not among the gene's GO annotations",
}


@dataclass
class Problem:
    curie: str
    kind: str          # human-readable problem type
    status: str
    claimed: Optional[str]
    actual: Optional[str]

    def __str__(self):
        # function-association: "GO:x "label": not among the gene's GO annotations (P04637)"
        if self.status == "SUPPORTED_FUNCTION_UNSUPPORTED":
            lbl = f' "{self.claimed}"' if self.claimed else ""
            gene = f" ({self.actual})" if self.actual else ""
            return f"{self.curie}{lbl}: {self.kind}{gene}"
        if self.claimed and self.actual:
            extra = f'  (said "{self.claimed}", actually "{self.actual}")'
        elif self.actual:
            extra = f'  (actually "{self.actual}")'
        elif self.claimed:
            extra = f'  (labeled "{self.claimed}")'
        else:
            extra = ""
        return f"{self.curie}: {self.kind}{extra}"


@dataclass
class Result:
    text: str
    n_ids: int
    problems: List[Problem]

    @property
    def ok(self) -> bool:
        """True if no problems were found."""
        return not self.problems

    def __bool__(self):
        return self.ok

    def __str__(self):
        if self.ok:
            return f"OK - {self.n_ids} identifier(s) checked, none flagged"
        lines = [f"{len(self.problems)} problem(s) in {self.n_ids} identifier(s):"]
        lines += [f"  - {p}" for p in self.problems]
        return "\n".join(lines)


def check(text, entity_hint=None, online=True, check_functions=False) -> Result:
    """Verify every biomedical identifier in `text`. Returns a Result.

    entity_hint: the gene/protein the text is about, if known (enables the
    wrong-gene check on free text).
    check_functions: also verify the target gene actually carries each GO term
    (opt-in; off by default so behaviour is unchanged).
    """
    verdicts = check_claims(text, online=online, entity_hint=entity_hint,
                            check_functions=check_functions)
    problems = [
        Problem(v.curie, _LABELS.get(v.status, v.status), v.status,
                v.claimed_label, v.canonical_label)
        for v in verdicts if v.status in FLAGGED_STATUSES
    ]
    return Result(text=text, n_ids=len(verdicts), problems=problems)


class Firewall:
    """Guard any function that returns model text.

        fw = Firewall()
        answer = fw.guard(call_my_llm)(prompt)   # raises if a fabrication slips through

    or non-raising:

        result = fw(answer_text)
    """

    def __init__(self, entity_hint=None, online=True, raise_on_flag=False,
                 check_functions=False):
        self.entity_hint = entity_hint
        self.online = online
        self.raise_on_flag = raise_on_flag
        self.check_functions = check_functions

    def __call__(self, text) -> Result:
        r = check(text, entity_hint=self.entity_hint, online=self.online,
                  check_functions=self.check_functions)
        if self.raise_on_flag and not r.ok:
            raise BioclaimFlag(r)
        return r

    def guard(self, fn):
        """Decorator: run fn, then verify its returned text."""
        def wrapped(*args, **kwargs):
            text = fn(*args, **kwargs)
            self(text)          # may raise if raise_on_flag
            return text
        return wrapped


class BioclaimFlag(Exception):
    def __init__(self, result: Result):
        self.result = result
        super().__init__(str(result))
