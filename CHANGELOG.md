# Changelog

## 0.2.0

### Added
- `PashtoNormalizer` for Standard (Kabul / Afghan) Pashto with three profiles: `unicode_only`, `standard`, `for_stemmer`.
- `changes()` lists every altered character with its original span and rule name, so spell checkers can show suggestions instead of hiding corrections; `normalize_token` leaves the original untouched; `explain` command.
- Opt-in `zwnj="smart"` and `tatweel="smart"` (off by default).
- Offset tracking: `normalize_with_offsets` and `original_span`.
- Folds Arabic presentation forms; removes ZWSP, BOM, LRM/RLM and other bidi controls.
- Urdu keyboard letters (`ٹ ڈ ڑ ے`), gaf canonicalization, alef and heh variants.
- Digit mode `"afghan"` (Arabic-Indic to Persian forms) and Urdu full stop to the dot.
- `audit` module and `audit` / `normalize` command line tools that stream files line by line.

### Design
- The normalizer answers only "what is the canonical form of this character?" It never corrects spelling or grammar.
- ZWNJ, tatweel and word spacing are **kept as written** by default; they can be spelling signals.
- The five yeh letters `ی ي ې ۍ ئ` are never merged by default.
- `ۀ` is kept; its decomposed form is composed to the same letter. Merge with `merge_heh_yeh=True`.
- Line breaks are kept; only horizontal whitespace is collapsed.
