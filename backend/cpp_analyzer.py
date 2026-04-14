"""
cpp_analyzer.py — Static analysis for C++ performance anti-patterns.

Detects common latency killers via regex pattern matching on code text.
Returns structured findings that can be merged into the LLM review or
consumed independently via the /api/analyze-cpp endpoint.

No external dependencies — pure stdlib.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional


# ─── Types ───────────────────────────────────────────────────────────

@dataclass
class Finding:
    line: int
    severity: str          # "low" | "medium" | "high"
    rule: str              # machine-readable rule id
    explanation: str       # why this is slow
    suggestion: str        # recommended fix
    snippet: str = ""      # the offending line (trimmed)


@dataclass
class AnalysisReport:
    file_path: str
    findings: List[Finding] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.findings)

    def by_severity(self, sev: str) -> List[Finding]:
        return [f for f in self.findings if f.severity == sev]

    def to_dicts(self) -> list:
        return [
            {
                "line": f.line,
                "severity": f.severity,
                "rule": f.rule,
                "explanation": f.explanation,
                "suggestion": f.suggestion,
                "snippet": f.snippet,
            }
            for f in self.findings
        ]


# ─── Helpers ─────────────────────────────────────────────────────────

def _stripped(line: str) -> str:
    """Return a whitespace-stripped, comment-free version of the line."""
    # Remove single-line comments
    idx = line.find("//")
    if idx != -1:
        line = line[:idx]
    return line.strip()


def _is_inside_loop(lines: List[str], target_idx: int) -> bool:
    """Heuristic: walk backwards from target_idx looking for an enclosing
    for/while/do scope that contains the target line."""
    brace_depth = 0
    for i in range(target_idx, -1, -1):
        s = _stripped(lines[i])
        brace_depth += s.count("}") - s.count("{")
        if brace_depth < 0:
            # We crossed into an enclosing scope — check if this line
            # or preceding lines (up to the opening keyword) are a loop.
            for j in range(i, -1, -1):
                sj = _stripped(lines[j])
                if re.search(r"\b(for|while|do)\b", sj):
                    return True
                # Stop at the previous statement boundary if we hit
                # another opening brace that isn't a loop/branch keyword
                if j < i and sj.endswith("{"):
                    break
            # Not a loop scope — reset depth and keep searching outward
            brace_depth = 0
    return False


# ─── Rules ───────────────────────────────────────────────────────────
# Each rule is a function(lines, start_line_offset) -> List[Finding]
# lines: list of code strings.  start_line_offset: 1-based line number
# of lines[0] in the original file.

def _rule_pass_by_value(lines: List[str], offset: int) -> List[Finding]:
    """Detect function params passing non-trivial types by value."""
    findings: List[Finding] = []
    heavy_types = (
        r"std::(?:string|vector|map|unordered_map|set|unordered_set|list|deque|"
        r"shared_ptr|unique_ptr|array|tuple|pair|optional|variant|any|"
        r"basic_string|multimap|multiset)"
    )
    # Match: type name( ... TypeName param ... )
    # We look for parameter lists containing heavy types NOT preceded by & or *
    param_re = re.compile(
        rf"(?:^|[,(])\s*(?:const\s+)?({heavy_types})<[^>]*>\s+(\w+)\s*(?=[,)])",
    )
    for i, line in enumerate(lines):
        s = _stripped(line)
        # Only check lines that look like function signatures
        if "(" not in s:
            continue
        for m in param_re.finditer(s):
            # Check there's no & or * right before the param name
            pre = s[:m.start(2)].rstrip()
            if pre and pre[-1] in ("&", "*"):
                continue
            findings.append(Finding(
                line=offset + i,
                severity="high",
                rule="pass_by_value",
                explanation=(
                    f"'{m.group(1)}' passed by value triggers a deep copy on every call. "
                    "In hot paths this causes heap allocations and cache thrashing."
                ),
                suggestion=f"Pass by const reference: `const {m.group(1)}<...>& {m.group(2)}`",
                snippet=s,
            ))
    return findings


def _rule_vector_no_reserve(lines: List[str], offset: int) -> List[Finding]:
    """Detect push_back/emplace_back inside loops without a preceding reserve()."""
    findings: List[Finding] = []
    push_re = re.compile(r"(\w+)\.(push_back|emplace_back)\s*\(")
    reserve_re = re.compile(r"(\w+)\.reserve\s*\(")

    # Collect all variable names that had reserve() called
    reserved_vars = set()
    for line in lines:
        for m in reserve_re.finditer(_stripped(line)):
            reserved_vars.add(m.group(1))

    for i, line in enumerate(lines):
        s = _stripped(line)
        for m in push_re.finditer(s):
            var = m.group(1)
            if var in reserved_vars:
                continue
            if _is_inside_loop(lines, i):
                findings.append(Finding(
                    line=offset + i,
                    severity="high",
                    rule="vector_no_reserve",
                    explanation=(
                        f"'{var}.{m.group(2)}()' inside a loop without prior reserve() "
                        "causes repeated reallocations — each one copies the entire buffer."
                    ),
                    suggestion=f"Call `{var}.reserve(expected_size)` before the loop.",
                    snippet=s,
                ))
    return findings


def _rule_map_over_unordered(lines: List[str], offset: int) -> List[Finding]:
    """Flag std::map where std::unordered_map may be faster."""
    findings: List[Finding] = []
    map_re = re.compile(r"\bstd::map\s*<")
    for i, line in enumerate(lines):
        s = _stripped(line)
        if map_re.search(s):
            findings.append(Finding(
                line=offset + i,
                severity="medium",
                rule="map_over_unordered_map",
                explanation=(
                    "std::map uses a red-black tree (O(log n) lookup). "
                    "std::unordered_map gives O(1) average lookup with better cache locality."
                ),
                suggestion=(
                    "Use std::unordered_map unless you need sorted iteration. "
                    "Similarly prefer std::unordered_set over std::set."
                ),
                snippet=s,
            ))
    return findings


def _rule_heap_alloc_in_loop(lines: List[str], offset: int) -> List[Finding]:
    """Detect heap allocations (new, malloc, make_shared, make_unique) inside loops."""
    findings: List[Finding] = []
    alloc_re = re.compile(
        r"\b(new\s+\w+|malloc\s*\(|calloc\s*\(|realloc\s*\("
        r"|std::make_shared\s*<|std::make_unique\s*<"
        r"|make_shared\s*<|make_unique\s*<)\b"
    )
    for i, line in enumerate(lines):
        s = _stripped(line)
        m = alloc_re.search(s)
        if m and _is_inside_loop(lines, i):
            findings.append(Finding(
                line=offset + i,
                severity="high",
                rule="heap_alloc_in_loop",
                explanation=(
                    f"Heap allocation ('{m.group(1).strip()}') inside a loop. "
                    "Each call hits the allocator, which may lock and always causes "
                    "cache misses on the new memory."
                ),
                suggestion=(
                    "Pre-allocate before the loop, use an object pool, or "
                    "switch to stack/arena allocation."
                ),
                snippet=s,
            ))
    return findings


def _rule_unnecessary_copy(lines: List[str], offset: int) -> List[Finding]:
    """Detect likely unnecessary copies of containers/strings."""
    findings: List[Finding] = []
    # Pattern: Type var = other_var;  (non-reference copy)
    copy_re = re.compile(
        r"\b(std::(?:string|vector|map|unordered_map|set|list|deque))"
        r"(?:<[^>]*>)?\s+(\w+)\s*=\s*(\w+)\s*;"
    )
    for i, line in enumerate(lines):
        s = _stripped(line)
        m = copy_re.search(s)
        if m:
            findings.append(Finding(
                line=offset + i,
                severity="medium",
                rule="unnecessary_copy",
                explanation=(
                    f"'{m.group(2)} = {m.group(3)}' copies the entire container. "
                    "If the source isn't needed afterwards, this wastes memory bandwidth."
                ),
                suggestion=(
                    f"Use `auto& {m.group(2)} = {m.group(3)};` for a reference, or "
                    f"`auto {m.group(2)} = std::move({m.group(3)});` to transfer ownership."
                ),
                snippet=s,
            ))
    return findings


def _rule_large_stack_alloc(lines: List[str], offset: int) -> List[Finding]:
    """Detect large C-style arrays on the stack."""
    findings: List[Finding] = []
    # Match: type name[NUMBER] where NUMBER > threshold
    arr_re = re.compile(r"\b\w+\s+\w+\s*\[\s*(\d+)\s*\]")
    threshold = 4096  # bytes (assuming 1-byte elements; real calc is hard)
    for i, line in enumerate(lines):
        s = _stripped(line)
        for m in arr_re.finditer(s):
            size = int(m.group(1))
            if size >= threshold:
                findings.append(Finding(
                    line=offset + i,
                    severity="medium",
                    rule="large_stack_alloc",
                    explanation=(
                        f"Stack array of {size} elements. Large stack allocations risk "
                        "stack overflow and blow out the L1 cache on entry."
                    ),
                    suggestion=(
                        "Use std::vector (heap, resizable) or a static/thread_local buffer "
                        "if the size is truly fixed."
                    ),
                    snippet=s,
                ))
    return findings


def _rule_mutex_in_loop(lines: List[str], offset: int) -> List[Finding]:
    """Detect lock acquisition inside tight loops."""
    findings: List[Finding] = []
    lock_re = re.compile(
        r"\b(std::lock_guard|std::unique_lock|std::scoped_lock|"
        r"lock_guard|unique_lock|scoped_lock|\.lock\s*\(\s*\))"
    )
    for i, line in enumerate(lines):
        s = _stripped(line)
        if lock_re.search(s) and _is_inside_loop(lines, i):
            findings.append(Finding(
                line=offset + i,
                severity="high",
                rule="mutex_in_tight_loop",
                explanation=(
                    "Acquiring a mutex inside a loop serialises every iteration and "
                    "causes kernel-mode transitions. Contention amplifies latency non-linearly."
                ),
                suggestion=(
                    "Hoist the lock outside the loop, batch updates, or use lock-free "
                    "structures (std::atomic, ring buffers)."
                ),
                snippet=s,
            ))
    return findings


def _rule_string_concat_in_loop(lines: List[str], offset: int) -> List[Finding]:
    """Detect string concatenation with += inside loops."""
    findings: List[Finding] = []
    concat_re = re.compile(r"(\w+)\s*\+=\s*(?:\"|\w)")
    for i, line in enumerate(lines):
        s = _stripped(line)
        m = concat_re.search(s)
        if m and _is_inside_loop(lines, i):
            # Heuristic: variable name likely a string
            findings.append(Finding(
                line=offset + i,
                severity="medium",
                rule="string_concat_in_loop",
                explanation=(
                    f"'{m.group(1)} +=' inside a loop may trigger repeated heap "
                    "reallocations as the string grows."
                ),
                suggestion=(
                    "Use std::ostringstream, or call .reserve() on the string with "
                    "the expected total size before the loop."
                ),
                snippet=s,
            ))
    return findings


def _rule_shared_ptr_overhead(lines: List[str], offset: int) -> List[Finding]:
    """Flag std::shared_ptr where unique_ptr might suffice."""
    findings: List[Finding] = []
    sp_re = re.compile(r"\bstd::shared_ptr\s*<")
    for i, line in enumerate(lines):
        s = _stripped(line)
        if sp_re.search(s):
            findings.append(Finding(
                line=offset + i,
                severity="low",
                rule="shared_ptr_overhead",
                explanation=(
                    "std::shared_ptr uses atomic reference counting (two cache lines: "
                    "control block + object). In single-owner scenarios this is wasted overhead."
                ),
                suggestion=(
                    "Prefer std::unique_ptr if ownership is not shared. "
                    "If shared access is needed, consider raw observer pointers for non-owning refs."
                ),
                snippet=s,
            ))
    return findings


def _rule_exception_in_loop(lines: List[str], offset: int) -> List[Finding]:
    """Detect try/catch blocks inside loops (exception machinery has cost)."""
    findings: List[Finding] = []
    try_re = re.compile(r"\btry\s*\{")
    for i, line in enumerate(lines):
        s = _stripped(line)
        if try_re.search(s) and _is_inside_loop(lines, i):
            findings.append(Finding(
                line=offset + i,
                severity="medium",
                rule="exception_in_loop",
                explanation=(
                    "try/catch inside a loop. While zero-cost exceptions have no "
                    "overhead on the happy path with modern ABIs, the compiler cannot "
                    "optimise across try-boundaries, and throwing is extremely expensive."
                ),
                suggestion=(
                    "Move the try/catch outside the loop or replace with "
                    "error codes / std::expected for hot paths."
                ),
                snippet=s,
            ))
    return findings


def _rule_virtual_dispatch(lines: List[str], offset: int) -> List[Finding]:
    """Flag virtual function declarations — informational for hot-path awareness."""
    findings: List[Finding] = []
    virt_re = re.compile(r"\bvirtual\s+\w+")
    for i, line in enumerate(lines):
        s = _stripped(line)
        if virt_re.search(s):
            findings.append(Finding(
                line=offset + i,
                severity="low",
                rule="virtual_dispatch",
                explanation=(
                    "Virtual dispatch uses an indirect call through the vtable. "
                    "This prevents inlining and causes a branch misprediction on first call."
                ),
                suggestion=(
                    "In latency-critical paths consider CRTP (static polymorphism), "
                    "std::variant + std::visit, or __attribute__((flatten))."
                ),
                snippet=s,
            ))
    return findings


def _rule_endl_vs_newline(lines: List[str], offset: int) -> List[Finding]:
    """Detect std::endl which flushes the stream buffer."""
    findings: List[Finding] = []
    endl_re = re.compile(r"\bstd::endl\b")
    for i, line in enumerate(lines):
        s = _stripped(line)
        if endl_re.search(s):
            findings.append(Finding(
                line=offset + i,
                severity="low",
                rule="endl_flush",
                explanation=(
                    "std::endl inserts a newline AND flushes the stream buffer. "
                    "Flushing is a syscall that stalls the pipeline."
                ),
                suggestion="Use '\\n' instead of std::endl unless you explicitly need a flush.",
                snippet=s,
            ))
    return findings


def _rule_inefficient_find(lines: List[str], offset: int) -> List[Finding]:
    """Detect std::find on associative containers (should use .find() member)."""
    findings: List[Finding] = []
    stdfind_re = re.compile(r"\bstd::find\s*\(")
    for i, line in enumerate(lines):
        s = _stripped(line)
        if stdfind_re.search(s):
            findings.append(Finding(
                line=offset + i,
                severity="medium",
                rule="inefficient_find",
                explanation=(
                    "std::find performs a linear O(n) scan. If the container is a map, set, "
                    "or unordered variant, use its .find() member for O(log n) or O(1) lookup."
                ),
                suggestion="Use container.find(key) instead of std::find(begin, end, key).",
                snippet=s,
            ))
    return findings


def _rule_move_semantics(lines: List[str], offset: int) -> List[Finding]:
    """Detect return of local containers that might benefit from explicit move."""
    findings: List[Finding] = []
    # Pattern: return localVar;  where a heavy type was declared earlier
    heavy_decl_re = re.compile(
        r"\b(?:std::(?:string|vector|map|unordered_map|set|list|deque))"
        r"(?:<[^>]*>)?\s+(\w+)"
    )
    declared_vars = set()
    for line in lines:
        for m in heavy_decl_re.finditer(_stripped(line)):
            declared_vars.add(m.group(1))

    return_re = re.compile(r"\breturn\s+(\w+)\s*;")
    for i, line in enumerate(lines):
        s = _stripped(line)
        m = return_re.search(s)
        if m and m.group(1) in declared_vars:
            # NRVO usually handles this, so keep severity low
            findings.append(Finding(
                line=offset + i,
                severity="low",
                rule="move_on_return",
                explanation=(
                    f"Returning local variable '{m.group(1)}'. Most compilers apply NRVO, "
                    "but complex control flow or multiple return paths can defeat it."
                ),
                suggestion=(
                    "Verify NRVO applies (single return path). If not, use "
                    f"`return std::move({m.group(1)});` — but only as a last resort."
                ),
                snippet=s,
            ))
    return findings


# ─── Rule Registry ───────────────────────────────────────────────────

ALL_RULES = [
    _rule_pass_by_value,
    _rule_vector_no_reserve,
    _rule_map_over_unordered,
    _rule_heap_alloc_in_loop,
    _rule_unnecessary_copy,
    _rule_large_stack_alloc,
    _rule_mutex_in_loop,
    _rule_string_concat_in_loop,
    _rule_shared_ptr_overhead,
    _rule_exception_in_loop,
    _rule_virtual_dispatch,
    _rule_endl_vs_newline,
    _rule_inefficient_find,
    _rule_move_semantics,
]


# ─── Public API ──────────────────────────────────────────────────────

def analyze_cpp(code: str, file_path: str = "<input>",
                start_line: int = 1) -> AnalysisReport:
    """Run all C++ performance rules against a block of code.

    Args:
        code: C++ source code as a string.
        file_path: File path for the report (cosmetic).
        start_line: 1-based line number of the first line in `code`,
                    used when analyzing a code block extracted from a diff.

    Returns:
        AnalysisReport with all findings sorted by line number.
    """
    lines = code.split("\n")
    report = AnalysisReport(file_path=file_path)

    for rule_fn in ALL_RULES:
        report.findings.extend(rule_fn(lines, start_line))

    # Sort by line, then severity (high first)
    severity_order = {"high": 0, "medium": 1, "low": 2}
    report.findings.sort(key=lambda f: (f.line, severity_order.get(f.severity, 3)))
    return report


def analyze_cpp_blocks(blocks: list, file_path: str = "<input>") -> AnalysisReport:
    """Convenience: run analysis over a list of CodeBlock objects.

    Merges findings from all blocks into one report.
    """
    report = AnalysisReport(file_path=file_path)
    for block in blocks:
        code = block.text if hasattr(block, "text") else "\n".join(block.get("lines", []))
        start = block.start_line if hasattr(block, "start_line") else block.get("start_line", 1)
        sub = analyze_cpp(code, file_path, start_line=start)
        report.findings.extend(sub.findings)

    severity_order = {"high": 0, "medium": 1, "low": 2}
    report.findings.sort(key=lambda f: (f.line, severity_order.get(f.severity, 3)))
    return report
