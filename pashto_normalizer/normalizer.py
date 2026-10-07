"""Normalization for Standard (Kabul / Afghan) Pashto.

What this module answers
------------------------
:class:`PashtoNormalizer` answers one question only:

    "What is the canonical representation of this character?"

It does **not** answer "is this word spelled correctly?" (a spell checker's job)
or "is this word right in this sentence?" (a grammar checker's job). So it never
silently corrects spelling. Things that can be a spelling or grammar signal are
**kept by default**: ZWNJ, tatweel, the five yeh letters, ``ۀ``, spacing. The
spell checker decides what to do with them. Use :meth:`PashtoNormalizer.changes`
to see exactly what was altered, so an editor can underline the original text and
offer the normalized form as a suggestion.

Layers
------
1. **Unicode layer** (safe, lossless in meaning): Arabic presentation forms,
   invisible and bidirectional control characters, combining-mark composition,
   horizontal whitespace. Profile: :meth:`PashtoNormalizer.unicode_only`.
2. **Kabul-standard orthography layer**: one canonical letter per character
   (``ك`` to ``ک``, ``گ`` to ``ګ``, Urdu ``ٹ ڈ ڑ ے`` to ``ټ ډ ړ ې``, Arabic-Indic
   digits to Persian digits, ``۔`` to ``.``, diacritics). Profile:
   :meth:`PashtoNormalizer.standard` (the default).
3. **Consumer views**: :meth:`PashtoNormalizer.for_stemmer` additionally removes
   ZWNJ and tatweel for dictionary and stem lookup.

Opt-in helpers
--------------
``zwnj="smart"`` and ``tatweel="smart"`` remove only marks with no visible effect
(and turn a standalone tatweel into a hyphen). They are off by default because
they change what the writer typed.

A fast path (:meth:`normalize`) and an offset-tracking path
(:meth:`normalize_with_offsets`) share the same code, so they always agree.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from .chars import ARABIC_DIGITS, LATIN_DIGITS, PERSIAN_DIGITS

ZWNJ = "‌"
TATWEEL = "ـ"

# --------------------------------------------------------------------------- #
# Character data
# --------------------------------------------------------------------------- #

# Arabic presentation forms (PDF / web copy). BOM (U+FEFF) is removed later.
_PRESENTATION = re.compile("[ﭐ-﷿ﹰ-﻾]")

# Invisible and bidirectional control characters that are never part of a word.
# ZWNJ (U+200C) is handled separately.
_INVISIBLE = re.compile(
    "[\u00ad\u200b\u200d\u200e\u200f\u202a-\u202e\u2060\u2066-\u2069\ufeff\u061c]"
)

# Combining marks that compose into a letter.
_COMPOSE = {
    "آ": "آ",  # ا + madda  -> آ
    "\u0627\u0654": "\u0623",  # alef + hamza above -> U+0623 (folded to bare alef only if unify_alef)
    "\u0627\u0655": "\u0625",  # alef + hamza below -> U+0625 (folded to bare alef only if unify_alef)
    "ؤ": "ؤ",  # و + hamza  -> ؤ
    "ئ": "ئ",  # ي + hamza  -> ئ
    "یٔ": "ئ",  # ی + hamza  -> ئ
    "هٔ": "ۀ",  # ه + hamza  -> ۀ
    "ۀ": "ۀ",  # ە + hamza  -> ۀ
}
_COMPOSE_RE = re.compile("|".join(map(re.escape, _COMPOSE)))

# Arabic marks (harakat, Quranic annotation, dagger alef). Combining hamza and
# madda are composed first, so any left over here are stray.
_DIACRITICS = re.compile(
    "[ؐ-ًؚ-ٰٟۖ-ۜ۟-۪ۤۧۨ-ۭ]"
)

# Letters that join only to the letter before them (never to the next one).
# ZWNJ after these has no visible effect.
_RIGHT_JOINING = frozenset(
    "ءآأإٱا"  # alef family and hamza
    "دذڈډڌڊڍڏڐڎۮ"  # dal family (incl. ډ)
    "رزژڑړڕږڙۯ"  # reh family (incl. ړ ږ)
    "وؤۄۅۆۇۈۉۊۋۏ"  # waw family
    "ەۀة"  # heh variants that do not join forward
    "ۃ"
)

_LETTER_RANGES = (
    ("ؠ", "ي"),
    ("ٮ", "ۓ"),
    ("ۺ", "ۿ"),
    ("ݐ", "ݿ"),
)


def _is_letter(ch: str) -> bool:
    if not ch:
        return False
    return any(lo <= ch <= hi for lo, hi in _LETTER_RANGES)


def _joins_forward(ch: str) -> bool:
    """True if ``ch`` is an Arabic-script letter that connects to the next letter."""
    return _is_letter(ch) and ch not in _RIGHT_JOINING


# 1:1 letter canonicalization -------------------------------------------------
_KAF = {"ك": "ک"}  # ك -> ک
_ALEF = {"أ": "ا", "إ": "ا", "ٱ": "ا"}  # أ إ ٱ -> ا
_MAKSURA = {"ى": "ی"}  # ى -> ی
_HEH = {
    "ة": "ه",  # ة
    "ہ": "ه",  # ہ
    "ۃ": "ه",  # ۃ
    "ھ": "ه",  # ھ
}
_HEH_YEH_MERGE = {"ۀ": "ه"}  # ۀ -> ه   (only when requested)
_GAF = {"گ": "ګ"}  # گ -> ګ
_URDU = {
    "ٹ": "ټ",  # ٹ -> ټ
    "ڈ": "ډ",  # ڈ -> ډ
    "ڑ": "ړ",  # ڑ -> ړ
    "ے": "ې",  # ے -> ې
}

_DIGIT_SETS = {"latin": LATIN_DIGITS, "arabic": ARABIC_DIGITS, "persian": PERSIAN_DIGITS}
_DIGIT_MODES = (None, "afghan", "persian", "arabic", "latin")

_ZWNJ_MODES = ("smart", "keep", "remove", "space")
_TATWEEL_MODES = ("smart", "keep", "remove")
_YEH_MODES = (None, "arabic", "persian", "all")

# Line-separator style characters that should become a real newline.
_LINE_SEPS = str.maketrans({" ": "\n", " ": "\n", "\x0b": "\n", "\x0c": "\n", "\x85": "\n"})

_Replacer = Callable[["re.Match[str]"], str]


@dataclass(frozen=True)
class Change:
    """One normalization change. ``start``/``end`` index the original text."""

    start: int
    end: int
    original: str
    replacement: str
    rule: str


_RULES = {
    "\u0643": "arabic-kaf",
    "\u0623": "alef-variant", "\u0625": "alef-variant", "\u0671": "alef-variant",
    "\u0649": "alef-maksura",
    "\u0629": "heh-variant", "\u06c1": "heh-variant", "\u06c3": "heh-variant", "\u06be": "heh-variant",
    "\u06c0": "heh-yeh",
    "\u06af": "gaf",
    "\u0679": "urdu-letter", "\u0688": "urdu-letter", "\u0691": "urdu-letter", "\u06d2": "urdu-letter",
    "\u06d4": "urdu-full-stop",
}


def _rule(orig: str, repl: str) -> str:
    """Name the rule behind one changed character."""
    if orig in _RULES:
        return _RULES[orig]
    if orig == ZWNJ:
        return "zwnj"
    if orig == TATWEEL:
        return "tatweel"
    if "\ufb50" <= orig <= "\ufdff" or "\ufe70" <= orig <= "\ufefe" and orig != "\ufeff":
        return "presentation-form"
    if _INVISIBLE.match(orig):
        return "invisible-character"
    if _DIACRITICS.match(orig):
        return "diacritic"
    if "\u0653" <= orig <= "\u0655":
        return "combining-mark"
    if orig.isspace():
        return "whitespace"
    if orig in ARABIC_DIGITS + PERSIAN_DIGITS + LATIN_DIGITS:
        return "digits"
    if orig in "\u064a\u06d0\u06cd\u0626\u06cc":
        return "yeh-ablation"
    return "other"


# --------------------------------------------------------------------------- #
# Offset-aware substitution helper
# --------------------------------------------------------------------------- #
def _sub(
    pattern: "re.Pattern[str]",
    repl: "str | _Replacer",
    text: str,
    idx: Optional[List[int]],
) -> Tuple[str, Optional[List[int]]]:
    """``pattern.sub`` that also keeps the original-offset list in sync.

    ``idx[i]`` is the position in the *original* text of ``text[i]``. When a
    match is replaced by a different-length string, every new character points
    at the first original character of the match.
    """
    if idx is None:
        return pattern.sub(repl, text), None
    out: List[str] = []
    new_idx: List[int] = []
    pos = 0
    for m in pattern.finditer(text):
        s, e = m.span()
        out.append(text[pos:s])
        new_idx.extend(idx[pos:s])
        r = repl(m) if callable(repl) else m.expand(repl)
        out.append(r)
        if len(r) == e - s:
            new_idx.extend(idx[s:e])
        elif r:
            new_idx.extend([idx[s]] * len(r))
        pos = e
    out.append(text[pos:])
    new_idx.extend(idx[pos:])
    return "".join(out), new_idx


class PashtoNormalizer:
    """Configurable Standard-Pashto text normalizer.

    The defaults are the recommended **standard** profile. Use
    :meth:`minimal` for Unicode clean-up only and :meth:`for_stemmer` for the
    stricter view a stemmer or dictionary lookup usually wants.

    Args:
        presentation_forms: fold Arabic presentation forms (PDF/web copy) to
            ordinary letters.
        remove_invisible: drop zero-width space/joiner, LRM/RLM and other bidi
            controls, word joiner, soft hyphen and BOM.
        zwnj: ``"keep"`` (default) leaves every ZWNJ as written. ``"smart"`` removes
            only ZWNJ with no visible effect (after a non-joining letter, at word
            edges, in runs) and keeps meaningful ones such as ``نه‌دی``. ``"remove"``
            or ``"space"`` apply to every ZWNJ.
        tatweel: ``"keep"`` (default) leaves every tatweel as written. ``"smart"``
            deletes elongation inside words and turns a standalone tatweel
            (``هند ـ ارام``) into a hyphen. ``"remove"`` deletes all.
        remove_diacritics: drop harakat and other Arabic marks.
        unify_kaf: ``ك`` to ``ک``.
        unify_alef: ``أ إ ٱ`` to ``ا`` (madda ``آ`` is kept).
        unify_maksura: ``ى`` to ``ی``.
        unify_heh: ``ة ہ ۃ ھ`` to ``ه``.
        merge_heh_yeh: ``ۀ`` to ``ه``. Off by default because ``ۀ`` can carry
            information; decide from corpus counts.
        canonicalize_gaf: ``گ`` to ``ګ`` (Standard Pashto letter).
        urdu_letters: Urdu keyboard letters ``ٹ ڈ ڑ ے`` to ``ټ ډ ړ ې``.
        unify_yeh: ``None`` (default, keep all five yeh letters). For ablation
            studies only: ``"arabic"`` (ی to ي), ``"persian"`` (ي to ی), ``"all"``
            (ي ې ۍ ئ to ی, destroys grammatical information).
        digits: ``"afghan"`` (default) folds Arabic-Indic digits ٠-٩ to the
            Persian forms ۰-۹ and leaves Latin digits alone. ``"persian"`` /
            ``"arabic"`` / ``"latin"`` fold every other family into that one.
            ``None`` leaves digits untouched.
        urdu_full_stop: ``۔`` to ``.`` (Afghan Pashto uses the dot).
        collapse_whitespace: collapse runs of horizontal whitespace (including
            NBSP and thin spaces) to one space and trim line edges.
        keep_newlines: keep line breaks (default). If False, they become spaces.
    """

    def __init__(
        self,
        presentation_forms: bool = True,
        remove_invisible: bool = True,
        zwnj: str = "keep",
        tatweel: str = "keep",
        remove_diacritics: bool = True,
        unify_kaf: bool = True,
        unify_alef: bool = True,
        unify_maksura: bool = True,
        unify_heh: bool = True,
        merge_heh_yeh: bool = False,
        canonicalize_gaf: bool = True,
        urdu_letters: bool = True,
        unify_yeh: Optional[str] = None,
        digits: Optional[str] = "afghan",
        urdu_full_stop: bool = True,
        collapse_whitespace: bool = True,
        keep_newlines: bool = True,
    ) -> None:
        if zwnj not in _ZWNJ_MODES:
            raise ValueError("zwnj must be one of %r" % (_ZWNJ_MODES,))
        if tatweel not in _TATWEEL_MODES:
            raise ValueError("tatweel must be one of %r" % (_TATWEEL_MODES,))
        if unify_yeh not in _YEH_MODES:
            raise ValueError("unify_yeh must be one of %r" % (_YEH_MODES,))
        if digits not in _DIGIT_MODES:
            raise ValueError("digits must be one of %r" % (_DIGIT_MODES,))

        self.config: Dict[str, Any] = dict(
            presentation_forms=presentation_forms,
            remove_invisible=remove_invisible,
            zwnj=zwnj,
            tatweel=tatweel,
            remove_diacritics=remove_diacritics,
            unify_kaf=unify_kaf,
            unify_alef=unify_alef,
            unify_maksura=unify_maksura,
            unify_heh=unify_heh,
            merge_heh_yeh=merge_heh_yeh,
            canonicalize_gaf=canonicalize_gaf,
            urdu_letters=urdu_letters,
            unify_yeh=unify_yeh,
            digits=digits,
            urdu_full_stop=urdu_full_stop,
            collapse_whitespace=collapse_whitespace,
            keep_newlines=keep_newlines,
        )
        self._table = str.maketrans(self._build_char_map())
        self._guard_yeh_forms()

    # ------------------------------------------------------------------ #
    # Profiles
    # ------------------------------------------------------------------ #
    @classmethod
    def standard(cls, **overrides: Any) -> "PashtoNormalizer":
        """Layers 1 + 2: the recommended Standard-Pashto profile (same as the default)."""
        return cls(**overrides)

    @classmethod
    def unicode_only(cls, **overrides: Any) -> "PashtoNormalizer":
        """Layer 1 only: Unicode clean-up and layout. No letter, mark or digit is changed."""
        base: Dict[str, Any] = dict(
            remove_diacritics=False,
            unify_kaf=False,
            unify_alef=False,
            unify_maksura=False,
            unify_heh=False,
            canonicalize_gaf=False,
            urdu_letters=False,
            digits=None,
            urdu_full_stop=False,
        )
        base.update(overrides)
        return cls(**base)

    @classmethod
    def for_stemmer(cls, **overrides: Any) -> "PashtoNormalizer":
        """Standard profile plus ZWNJ and tatweel removed (use on single words, after splitting)."""
        base: Dict[str, Any] = dict(zwnj="remove", tatweel="remove")
        base.update(overrides)
        return cls(**base)

    # ------------------------------------------------------------------ #
    # Compilation
    # ------------------------------------------------------------------ #
    def _build_char_map(self) -> Dict[str, str]:
        c = self.config
        m: Dict[str, str] = {}
        if c["unify_kaf"]:
            m.update(_KAF)
        if c["unify_alef"]:
            m.update(_ALEF)
        if c["unify_maksura"]:
            m.update(_MAKSURA)
        if c["unify_heh"]:
            m.update(_HEH)
        if c["merge_heh_yeh"]:
            m.update(_HEH_YEH_MERGE)
        if c["canonicalize_gaf"]:
            m.update(_GAF)
        if c["urdu_letters"]:
            m.update(_URDU)
        if c["unify_yeh"] == "arabic":
            m["ی"] = "ي"
        elif c["unify_yeh"] == "persian":
            m["ي"] = "ی"
        elif c["unify_yeh"] == "all":
            for y in "يېۍئ":
                m[y] = "ی"
        digits = c["digits"]
        if digits == "afghan":
            m.update(zip(ARABIC_DIGITS, PERSIAN_DIGITS))
        elif digits:
            target = _DIGIT_SETS[digits]
            for name, src in _DIGIT_SETS.items():
                if name != digits:
                    m.update(zip(src, target))
        return m

    def _guard_yeh_forms(self) -> None:
        """Refuse to build a map that merges yeh letters unless explicitly asked."""
        if self.config["unify_yeh"] is not None:
            return
        touched = [y for y in "\u064a\u06d0\u06cd\u0626" if ord(y) in self._table]
        if touched or ord("\u06cc") in self._table:  # pragma: no cover - defensive
            raise RuntimeError("a yeh letter entered the character map: %r" % (touched,))

    # ------------------------------------------------------------------ #
    # Context-dependent rules
    # ------------------------------------------------------------------ #
    def _zwnj_repl(self, m: "re.Match[str]") -> str:
        mode = self.config["zwnj"]
        if mode == "remove":
            return ""
        if mode == "space":
            return " "
        s = m.string
        prev = s[m.start() - 1] if m.start() > 0 else ""
        nxt = s[m.end()] if m.end() < len(s) else ""
        keep = _joins_forward(prev) and _is_letter(nxt) and nxt != "ء"
        return ZWNJ if keep else ""

    @staticmethod
    def _tatweel_smart(m: "re.Match[str]") -> str:
        s = m.string
        prev = s[m.start() - 1] if m.start() > 0 else ""
        nxt = s[m.end()] if m.end() < len(s) else ""
        alone = (prev == "" or prev.isspace()) and (nxt == "" or nxt.isspace())
        return "-" if alone else ""

    # ------------------------------------------------------------------ #
    # Pipeline
    # ------------------------------------------------------------------ #
    def _run(self, text: str, idx: Optional[List[int]]) -> Tuple[str, Optional[List[int]]]:
        c = self.config

        if c["presentation_forms"]:
            text, idx = _sub(
                _PRESENTATION, lambda m: unicodedata.normalize("NFKC", m.group()), text, idx
            )
        if c["remove_invisible"]:
            text, idx = _sub(_INVISIBLE, "", text, idx)

        text, idx = _sub(_COMPOSE_RE, lambda m: _COMPOSE[m.group()], text, idx)
        if c["remove_diacritics"]:
            text, idx = _sub(_DIACRITICS, "", text, idx)

        if self._table:
            text = text.translate(self._table)  # 1:1, offsets unchanged

        if c["tatweel"] == "remove":
            text, idx = _sub(re.compile(TATWEEL + "+"), "", text, idx)
        elif c["tatweel"] == "smart":
            text, idx = _sub(re.compile(TATWEEL + "+"), self._tatweel_smart, text, idx)

        if c["zwnj"] != "keep":
            text, idx = _sub(re.compile(ZWNJ + "+"), self._zwnj_repl, text, idx)

        # Removing ZWNJ or tatweel can make a base letter and its hamza adjacent.
        text, idx = _sub(_COMPOSE_RE, lambda m: _COMPOSE[m.group()], text, idx)
        if self._table:
            text = text.translate(self._table)

        if c["urdu_full_stop"]:
            text = text.replace("۔", ".")

        text = text.translate(_LINE_SEPS)
        if c["collapse_whitespace"]:
            text, idx = self._whitespace(text, idx)
        return text, idx

    def _whitespace(self, text: str, idx: Optional[List[int]]) -> Tuple[str, Optional[List[int]]]:
        if self.config["keep_newlines"]:
            text, idx = _sub(re.compile(r"\r\n|\r"), "\n", text, idx)
            text, idx = _sub(re.compile(r"[^\S\n]+"), " ", text, idx)
            text, idx = _sub(re.compile(r" ?\n ?"), "\n", text, idx)
            text, idx = _sub(re.compile(r"\n{3,}"), "\n\n", text, idx)
        else:
            text, idx = _sub(re.compile(r"\s+"), " ", text, idx)
        text, idx = _sub(re.compile(r"\A\s+|\s+\Z"), "", text, idx)
        return text, idx

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def __call__(self, text: str) -> str:
        return self.normalize(text)

    def normalize(self, text: str) -> str:
        """Return the normalized text."""
        if not text:
            return text
        return self._run(text, None)[0]

    def normalize_with_offsets(self, text: str) -> Tuple[str, List[int]]:
        """Return ``(normalized, offsets)``.

        ``offsets[i]`` is the index in the original ``text`` of the character that
        produced ``normalized[i]``. Use :meth:`original_span` to map a span.
        """
        if not text:
            return text, []
        out, idx = self._run(text, list(range(len(text))))
        assert idx is not None
        return out, idx

    @staticmethod
    def original_span(offsets: List[int], start: int, end: int) -> Tuple[int, int]:
        """Map a span of the normalized text back to the original text."""
        if start >= end or not offsets:
            return (offsets[start] if start < len(offsets) else 0,) * 2
        return offsets[start], offsets[end - 1] + 1

    def normalize_token(self, token: str) -> str:
        """Normalize a single word. The original string is not modified."""
        return self.normalize(token)

    def changes(self, text: str) -> List["Change"]:
        """List every character that normalization changes, with a rule name.

        Spans refer to the **original** text. A spell checker or editor can underline
        ``text[c.start:c.end]`` and offer ``c.replacement`` as a suggestion instead of
        pretending the original never existed.
        """
        if not text:
            return []
        out, idx = self.normalize_with_offsets(text)
        first: Dict[int, int] = {}
        for i, o in enumerate(idx):
            first.setdefault(o, i)
        result: List[Change] = []
        for j, ch in enumerate(text):
            if j in first:
                repl = out[first[j]]
                if repl != ch:
                    result.append(Change(j, j + 1, ch, repl, _rule(ch, repl)))
            else:
                rule = _rule(ch, "")
                prev = result[-1] if result else None
                if prev and prev.end == j and prev.replacement == "" and prev.rule == rule:
                    result[-1] = Change(prev.start, j + 1, prev.original + ch, "", rule)
                else:
                    result.append(Change(j, j + 1, ch, "", rule))
        return result

    def is_normalized(self, text: str) -> bool:
        """True if normalizing ``text`` would not change it."""
        return self.normalize(text) == text

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.config)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PashtoNormalizer":
        known = set(cls().config)
        return cls(**{k: v for k, v in data.items() if k in known})
