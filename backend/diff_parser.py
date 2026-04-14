"""
diff_parser.py — Parse GitHub unified diffs into structured code blocks.

Extracts added/modified code, detects file language (C++/Python),
and returns typed objects the analyzer can consume directly.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


# ─── Types ───────────────────────────────────────────────────────────

class Language(str, Enum):
    PYTHON = "python"
    CPP = "cpp"
    UNKNOWN = "unknown"


class ChangeType(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"


@dataclass
class CodeBlock:
    """A contiguous block of added or modified code within a single hunk."""
    lines: List[str]
    start_line: int
    end_line: int
    change_type: ChangeType

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def line_count(self) -> int:
        return len(self.lines)


@dataclass
class FileDiff:
    """All changes for one file in the pull request."""
    path: str
    language: Language
    blocks: List[CodeBlock] = field(default_factory=list)

    @property
    def total_added_lines(self) -> int:
        return sum(b.line_count for b in self.blocks if b.change_type == ChangeType.ADDED)

    @property
    def total_modified_lines(self) -> int:
        return sum(b.line_count for b in self.blocks if b.change_type == ChangeType.MODIFIED)


@dataclass
class ParsedDiff:
    """Top-level result returned by parse_diff."""
    files: List[FileDiff] = field(default_factory=list)

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def total_blocks(self) -> int:
        return sum(len(f.blocks) for f in self.files)

    def files_by_language(self, lang: Language) -> List[FileDiff]:
        return [f for f in self.files if f.language == lang]


# ─── Language Detection ──────────────────────────────────────────────

_EXTENSION_MAP: dict[str, Language] = {
    ".py": Language.PYTHON,
    ".pyw": Language.PYTHON,
    ".pyi": Language.PYTHON,
    ".cpp": Language.CPP,
    ".cxx": Language.CPP,
    ".cc": Language.CPP,
    ".c": Language.CPP,
    ".hpp": Language.CPP,
    ".hxx": Language.CPP,
    ".h": Language.CPP,
}


def detect_language(file_path: str) -> Language:
    """Detect language from file extension."""
    _, ext = os.path.splitext(file_path.lower())
    return _EXTENSION_MAP.get(ext, Language.UNKNOWN)


# ─── Hunk Header Parsing ────────────────────────────────────────────

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def _parse_hunk_start(line: str) -> Optional[int]:
    """Extract the new-file start line from a hunk header.

    Example: '@@ -10,7 +15,9 @@' → 15
    """
    m = _HUNK_RE.match(line)
    return int(m.group(1)) if m else None


# ─── Core Parser ─────────────────────────────────────────────────────

def _flush_block(
    block_lines: List[str],
    block_start: int,
    current_line: int,
    has_context: bool,
) -> Optional[CodeBlock]:
    """Flush accumulated added lines into a CodeBlock."""
    if not block_lines:
        return None
    change_type = ChangeType.MODIFIED if has_context else ChangeType.ADDED
    return CodeBlock(
        lines=list(block_lines),
        start_line=block_start,
        end_line=current_line - 1,
        change_type=change_type,
    )


def _parse_file_hunks(hunk_lines: List[str]) -> List[CodeBlock]:
    """Walk diff lines for a single file and extract CodeBlocks."""
    blocks: List[CodeBlock] = []
    current_new_line = 1
    block_buf: List[str] = []
    block_start = 1
    has_context_before = False
    saw_removal = False

    for raw_line in hunk_lines:
        # New hunk header resets position tracking
        hunk_start = _parse_hunk_start(raw_line)
        if hunk_start is not None:
            # Flush any pending block
            blk = _flush_block(block_buf, block_start, current_new_line, saw_removal or has_context_before)
            if blk:
                blocks.append(blk)
            block_buf.clear()
            current_new_line = hunk_start
            has_context_before = False
            saw_removal = False
            continue

        if raw_line.startswith("+"):
            # Added line (strip the leading '+')
            content = raw_line[1:]
            if not block_buf:
                block_start = current_new_line
            block_buf.append(content)
            current_new_line += 1

        elif raw_line.startswith("-"):
            # Removed line — doesn't advance new-file counter
            # but if additions follow, they count as *modified*
            saw_removal = True

        else:
            # Context line (starts with ' ' or is blank)
            blk = _flush_block(block_buf, block_start, current_new_line, saw_removal or has_context_before)
            if blk:
                blocks.append(blk)
            block_buf.clear()
            has_context_before = True
            saw_removal = False
            current_new_line += 1

    # Flush remaining
    blk = _flush_block(block_buf, block_start, current_new_line, saw_removal or has_context_before)
    if blk:
        blocks.append(blk)

    return blocks


# ─── Public API ──────────────────────────────────────────────────────

def parse_diff(raw_diff: str) -> ParsedDiff:
    """Parse a unified diff string into structured FileDiff objects.

    Args:
        raw_diff: Full unified diff text (e.g. from GitHub API).

    Returns:
        ParsedDiff containing one FileDiff per changed file,
        each with language detection and extracted code blocks.
    """
    result = ParsedDiff()
    if not raw_diff or not raw_diff.strip():
        return result

    lines = raw_diff.split("\n")
    current_path: Optional[str] = None
    hunk_buf: List[str] = []

    for line in lines:
        # Detect file boundary: 'diff --git a/path b/path'
        if line.startswith("diff --git "):
            # Flush previous file
            if current_path is not None:
                lang = detect_language(current_path)
                blocks = _parse_file_hunks(hunk_buf)
                if blocks:
                    result.files.append(FileDiff(path=current_path, language=lang, blocks=blocks))

            # Extract new path from 'b/...'
            parts = line.split(" b/", 1)
            current_path = parts[1] if len(parts) == 2 else None
            hunk_buf.clear()
            continue

        # Skip diff metadata lines
        if line.startswith("index ") or line.startswith("--- ") or line.startswith("+++ "):
            continue

        # Everything else goes into the hunk buffer
        hunk_buf.append(line)

    # Flush last file
    if current_path is not None:
        lang = detect_language(current_path)
        blocks = _parse_file_hunks(hunk_buf)
        if blocks:
            result.files.append(FileDiff(path=current_path, language=lang, blocks=blocks))

    return result


def format_blocks_for_analysis(parsed: ParsedDiff) -> str:
    """Format parsed diff into a structured string for LLM analysis.

    Groups code blocks by file with language tags, making it easier
    for the analyzer to understand context and provide line-accurate feedback.
    """
    sections: List[str] = []

    for f in parsed.files:
        header = f"### File: {f.path}  [lang={f.language.value}]"
        file_blocks: List[str] = []

        for b in f.blocks:
            tag = b.change_type.value.upper()
            file_blocks.append(
                f"[{tag}] Lines {b.start_line}-{b.end_line}:\n"
                f"```{f.language.value}\n{b.text}\n```"
            )

        if file_blocks:
            sections.append(header + "\n" + "\n".join(file_blocks))

    return "\n\n".join(sections) if sections else "(empty diff)"
