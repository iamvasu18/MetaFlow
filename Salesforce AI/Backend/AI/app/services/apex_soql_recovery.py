"""Conservative local correction for a specific unambiguous SOQL clause-order error.

This is NOT a replacement for Salesforce check-only validation. Never rewrite
arbitrary SOQL or touch quoted strings and comments.
"""
import re
from Backend.AI.app.services.apex_validator import lexical_source

_BAD = re.compile(r'\bWITH\s+(?:USER_MODE|SYSTEM_MODE)\s+(?=WHERE\b)', re.I)
_ORDER = re.compile(r'\b(?:GROUP\s+BY|HAVING|ORDER\s+BY|LIMIT|OFFSET|FOR\s+UPDATE|ALL\s+ROWS)\b', re.I)


def correct_user_mode_order(source: str) -> tuple[str, int]:
    """Move a misplaced access-mode clause after the query's WHERE condition.

    Only handles queries with a clear WHERE and no ambiguity in their lexical
    structure. Leaves everything else unchanged for AI/Salesforce validation.
    """
    masked, errors = lexical_source(source)
    if errors:
        return source, 0
    edits = []
    for match in re.finditer(r'\[\s*SELECT\b.*?\]', masked, re.I | re.S):
        segment = masked[match.start():match.end()]
        bad = _BAD.search(segment)
        if not bad:
            continue
        # Only modify exactly one misplaced mode clause, and stop at the first
        # following sorting/pagination clause. The remainder is not changed.
        where = re.match(r'\s*WHERE\b', segment[bad.end():], re.I)
        if not where or len(re.findall(r'\bWITH\s+(?:USER_MODE|SYSTEM_MODE)\b', segment, re.I)) != 1:
            continue
        later = segment[bad.end():]
        boundary = _ORDER.search(later)
        insertion = match.start() + bad.end() + (boundary.start() if boundary else len(later) - 1)
        start, end = match.start() + bad.start(), match.start() + bad.end()
        if insertion <= end:
            continue
        clause = source[start:end].strip()
        edits.append((start, end, insertion, clause))
    for start, end, insertion, clause in reversed(edits):
        # Reverse-order edits preserve earlier offsets and original formatting.
        # Preserve the intervening WHERE condition exactly, except whitespace.
        between = source[end:insertion].rstrip()
        source = source[:start] + between + '\n        ' + clause + ' ' + source[insertion:]
    return source, len(edits)
