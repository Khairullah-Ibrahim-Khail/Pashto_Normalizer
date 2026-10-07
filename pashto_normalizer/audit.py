"""Corpus audit: which characters does a text collection contain?

Run this on a corpus *before* choosing normalization rules. Characters outside
the expected Standard-Pashto inventory show exactly which rules matter.
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from typing import Dict, Iterable, List, Tuple

from .chars import PASHTO_ALPHABET

# Characters expected in clean Standard Pashto text (besides spaces and newlines).
EXPECTED = frozenset(
    "".join(PASHTO_ALPHABET)
    + "۰۱۲۳۴۵۶۷۸۹0123456789"
    + "،؛؟.,:;!?-()[]{}\"'«»…/%"
    + "‌"  # ZWNJ is meaningful and expected
)

# Short explanations for the most common unexpected characters.
HINTS: Dict[str, str] = {
    "ك": "Arabic kaf (becomes ک)",
    "گ": "Persian gaf (becomes ګ)",
    "ٹ": "Urdu ٹ (becomes ټ)",
    "ڈ": "Urdu ڈ (becomes ډ)",
    "ڑ": "Urdu ڑ (becomes ړ)",
    "ے": "Urdu ے (becomes ې)",
    "۔": "Urdu full stop ۔ (becomes .)",
    "ـ": "tatweel",
    "\u200b": "zero-width space",
    "\u200d": "zero-width joiner",
    "\u200e": "left-to-right mark",
    "\u200f": "right-to-left mark",
    "\ufeff": "BOM",
    "\u00a0": "no-break space",
    "ى": "alef maksura (becomes ی)",
    "ہ": "Urdu heh goal (becomes ه)",
    "ھ": "heh doachashmee (becomes ه)",
    "ة": "ta marbuta (becomes ه)",
}


def char_inventory(lines: Iterable[str]) -> Counter:
    """Count every character in ``lines`` (newlines excluded). Streams, so any size."""
    counts: Counter = Counter()
    for line in lines:
        counts.update(line.rstrip("\n"))
    return counts


def describe(ch: str) -> str:
    name = unicodedata.name(ch, "UNNAMED")
    return HINTS.get(ch, name.lower())


def unexpected(counts: Counter) -> List[Tuple[str, int]]:
    """Characters not in the expected inventory, most frequent first."""
    rows = [
        (ch, n)
        for ch, n in counts.items()
        if ch not in EXPECTED and not ch.isspace()
    ]
    rows.sort(key=lambda r: -r[1])
    return rows


def report(counts: Counter, top: int = 40) -> str:
    """Human-readable audit report."""
    total = sum(counts.values())
    rows = unexpected(counts)
    out = [f"characters: {total}   distinct: {len(counts)}   unexpected distinct: {len(rows)}"]
    if not rows:
        out.append("no unexpected characters")
        return "\n".join(out)
    out.append("")
    out.append(f"{'char':<6}{'code':<9}{'count':>10}  meaning")
    for ch, n in rows[:top]:
        shown = ch if ch.isprintable() and not unicodedata.combining(ch) else "·"
        out.append(f"{shown:<6}U+{ord(ch):04X}  {n:>10}  {describe(ch)}")
    if len(rows) > top:
        out.append(f"... and {len(rows) - top} more")
    return "\n".join(out)
