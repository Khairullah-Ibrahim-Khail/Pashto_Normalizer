<div align="center">

# Pashto_Normalizer

**A text normalizer for Standard (Kabul / Afghan) Pashto.**
Pure Python · zero dependencies · Python 3.8+

[![Tests](https://github.com/Khairullah-Ibrahim-Khail/Pashto_Normalizer/actions/workflows/tests.yml/badge.svg)](https://github.com/Khairullah-Ibrahim-Khail/Pashto_Normalizer/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

</div>

---

## Why this exists

Pashto text on the web is messy. The same word appears with Arabic, Persian or Urdu letters, hidden zero-width characters, PDF presentation forms and inconsistent digits. Any later step (spell checking, grammar checking, stemming, training a model) inherits that noise.

Pashto_Normalizer cleans it in one deterministic, local step, and it is built to be **shared** by those later steps.

## Design principle

The normalizer answers exactly one question:

> **"What is the canonical representation of this character?"**

It does **not** answer "is this word spelled correctly?" (a spell checker's job) or "is this word right in this sentence?" (a grammar checker's job). So it never silently corrects spelling:

- `گ → ګ` is normalization. For Kabul Standard Pashto there is one canonical letter.
- `سړي → سړی` is **never** normalization. Whether one form is right depends on the word and the sentence, so that is for a spell or grammar checker.
- `ZWNJ`, tatweel, spacing and the five yeh letters are kept exactly as written, because they can be a spelling signal.

```text
                    Raw Pashto text
                           │
                           ▼
              ┌──────────────────────┐
              │   Unicode layer      │   safe, lossless in meaning
              └──────────┬───────────┘
                         ▼
              ┌──────────────────────┐
              │ Kabul-standard       │   one canonical letter per character
              │ orthography layer    │
              └──────────┬───────────┘
                         │
             ┌───────────┼────────────┐
             ▼           ▼            ▼
        Spell checker  Grammar     Stemmer
                       checker
```

The original text is never thrown away. `changes()` lists every character that was altered, so an editor can underline the original and offer the normalized form as a suggestion (see [Seeing what changed](#seeing-what-changed)).

## Contents

- [Design principle](#design-principle)
- [Install](#install)
- [Quick start](#quick-start)
- [What it does](#what-it-does)
- [What is never changed](#what-is-never-changed)
- [Profiles](#profiles)
- [Seeing what changed](#seeing-what-changed)
- [All options](#all-options)
- [Mapping results back to the original text](#mapping-results-back-to-the-original-text)
- [Command line](#command-line)
- [Working with big files](#working-with-big-files)
- [Project layout](#project-layout)
- [Tests](#tests)
- [Limits](#limits)
- [Contributing](#contributing)
- [License](#license)

## Install

```bash
git clone https://github.com/Khairullah-Ibrahim-Khail/Pashto_Normalizer.git
cd Pashto_Normalizer
pip install .
```

Or run it straight from the folder with `python -m pashto_normalizer`, no install needed.

## Quick start

```python
from pashto_normalizer import PashtoNormalizer

norm = PashtoNormalizer()

norm("پاكستان ٢٠٢٦")            # Arabic kaf, Arabic-Indic digits
# 'پاکستان ۲۰۲۶'

norm("گلبهار ٹول")              # Persian gaf, Urdu keyboard letter
# 'ګلبهار ټول'

norm("هند ـ ارام")              # tatweel is kept exactly as written
# 'هند ـ ارام'
```

One-liner for single calls:

```python
import pashto_normalizer
pashto_normalizer.normalize("پاكستان")   # 'پاکستان'
```

## What it does

### Letters changed to the canonical form

| Input | Output | Rule |
|---|---|---|
| `پاكستان` | `پاکستان` | Arabic kaf `ك` to `ک` |
| `كتاب` | `کتاب` | Arabic kaf `ك` to `ک` |
| `گلبهار` | `ګلبهار` | Persian gaf `گ` to Pashto `ګ` |
| `گاډی` | `ګاډی` | Persian gaf `گ` to Pashto `ګ` |
| `ٹول` | `ټول` | Urdu keyboard `ٹ` to `ټ` |
| `ڈاکټر` | `ډاکټر` | Urdu keyboard `ڈ` to `ډ` |
| `ڑوند` | `ړوند` | Urdu keyboard `ڑ` to `ړ` |
| `ښکلے` | `ښکلې` | Urdu keyboard `ے` to `ې` |
| `أمریکا` | `امریکا` | Alef with hamza to bare alef (madda `آ` is kept) |
| `إسلام` | `اسلام` | Alef with hamza to bare alef |
| `موسى` | `موسی` | Alef maksura `ى` to `ی` |
| `ہند` | `هند` | Urdu heh `ہ` to `ه` |
| `مدرسة` | `مدرسه` | Ta marbuta `ة` to `ه` |
| `ھغه` | `هغه` | Heh doachashmee `ھ` to `ه` |

### Digits and punctuation

| Input | Output | Rule |
|---|---|---|
| `٢٠٢٦ کال` | `۲۰۲۶ کال` | Arabic-Indic digits to Afghan (Persian) digits |
| `٣٥ تنه` | `۳۵ تنه` | Arabic-Indic digits to Afghan (Persian) digits |
| `ښه ده۔` | `ښه ده.` | Urdu full stop `۔` to the dot |

### Unicode clean-up

| Input | Output | Rule |
|---|---|---|
| `ﻛﺎﺑﻠ` | `کابل` | Arabic presentation form (PDF copy) folded to ordinary letters, then `ك` to `ک` |
| `ﻟﺎﺳ` | `لاس` | Arabic presentation form folded |
| `مُدَّت` | `مدت` | Diacritics removed |
| `زَه` | `زه` | Diacritics removed |
| `کابل` + two tabs and a space + `ښار` | `کابل ښار` | Tabs and repeated spaces collapse to one space |
| `کابل` + a no-break space + `ښار` | `کابل ښار` | No-break space becomes a normal space |

Invisible characters (zero-width space, joiner, left-to-right and right-to-left marks, bidi controls, BOM, soft hyphen) are removed too. They cannot be seen, so they are never a spelling signal.

### Kept exactly as written

These are left alone on purpose. They can be spelling or grammar signals, so they belong to the spell checker and grammar checker, not the normalizer.

| Input | Output | Why |
|---|---|---|
| `سړی` | `سړی` | Yeh letters carry grammar: `ی` is not merged with `ي` |
| `سړي` | `سړي` | Masculine plural / oblique `ي` stays |
| `ښکلې` | `ښکلې` | `ې` stays |
| `نجلۍ` | `نجلۍ` | `ۍ` stays |
| `کوي` | `کوي` | `ي` stays |
| `ټ ډ ړ ږ ښ څ ځ ګ ڼ` | `ټ ډ ړ ږ ښ څ ځ ګ ڼ` | Pashto-specific letters are never folded |
| `هغۀ` | `هغۀ` | `ۀ` is kept (merge with `merge_heh_yeh=True`) |
| `کا‌بل` | `کا‌بل` | ZWNJ kept: `کا‌بل` and `کابل` are different strings; which is right is a spelling question |
| `نه‌دی` | `نه‌دی` | ZWNJ kept |
| `له‌منځه` | `له‌منځه` | ZWNJ kept |
| `ماه‌رنګ` | `ماه‌رنګ` | ZWNJ kept |
| `حزب‌الله` | `حزب‌الله` | ZWNJ kept |
| `هند ـ ارام` | `هند ـ ارام` | Tatweel kept |
| `افغانســـتان` | `افغانســـتان` | Tatweel kept |
| `یو ځای` | `یو ځای` | Spacing is not touched: `یو ځای` and `یوځای` are both left alone |
| `یوځای` | `یوځای` | Spacing is not touched |
| `کړکي` | `کړکي` | Spelling is not corrected (`کړکې` is a spell checker's decision) |
| `۱۴۰۵ کال` | `۱۴۰۵ کال` | Persian digits are already canonical |
| `Kabul 2026` | `Kabul 2026` | Latin text and Latin digits are left alone |
| `کابل، ښار؟` | `کابل، ښار؟` | Pashto punctuation is left alone |

### Opt-in cleaning

Nothing here runs by default. Ask for it when you know your text needs it.

| Input | Option | Output | What it does |
|---|---|---|---|
| `کا‌بل` | `zwnj="smart"` | `کابل` | ZWNJ after a non-joining letter has no visible effect |
| `نه‌دی` | `zwnj="smart"` | `نه‌دی` | ZWNJ that separates joining letters is meaningful, so it stays |
| `نه‌دی` | `zwnj="remove"` | `نهدی` | Remove every ZWNJ |
| `نه‌دی` | `zwnj="space"` | `نه دی` | Turn every ZWNJ into a space |
| `افغانســـتان` | `tatweel="smart"` | `افغانستان` | Remove tatweel inside words |
| `هند ـ ارام` | `tatweel="smart"` | `هند - ارام` | A standalone tatweel becomes a hyphen |
| `هند ـ ارام` | `tatweel="remove"` | `هند ارام` | Remove every tatweel |
| `هغۀ` | `merge_heh_yeh=True` | `هغه` | Merge `ۀ` into `ه` |
| `مُدَّت` | `remove_diacritics=False` | `مُدَّت` | Keep diacritics |
| `٢٠٢٦` | `digits=None` | `٢٠٢٦` | Arabic-Indic digits to Persian digits is the default; turn digit folding off |
| `۲۰۲۶` | `digits="latin"` | `2026` | Fold every digit family to Latin |
| `پاكستان` | `unicode_only()` | `پاكستان` | Unicode layer only: no letter is changed |
| `نه‌دی` | `for_stemmer()` | `نهدی` | Stemmer view: ZWNJ and tatweel removed |
| `سړي ښکلې` | `unify_yeh="all"` | `سړی ښکلی` | Ablation only: destroys grammar (never use in production) |

## What is never changed

- The five yeh letters `ی ي ې ۍ ئ` stay distinct. They carry gender, number and case (`سړی` / `سړي` / `ښکلې` / `نجلۍ`).
- Pashto-specific consonants `ټ ډ ړ ږ ښ څ ځ ګ ڼ` are never folded to look-alike Arabic or Persian letters.
- `ۀ` is kept, and its decomposed form (`ه` + hamza mark) is composed to the same `ۀ`. Merge it with `merge_heh_yeh=True` once your corpus counts show it is safe.
- ZWNJ, tatweel and spacing between words are not touched by default.
- Latin digits and Latin text are left alone.
- Spelling is not corrected (see [Limits](#limits)).

## Profiles

```python
PashtoNormalizer.unicode_only()   # Unicode layer only: no letter, mark or digit is changed
PashtoNormalizer.standard()       # Unicode + Kabul-standard layers (the default)
PashtoNormalizer.for_stemmer()    # standard + ZWNJ and tatweel removed, for dictionary and stem lookup
```

`for_stemmer()` is meant for single words after they have been split. Do not use it before a spell or grammar checker, because it removes signals they need.

Opt-in cleaning for text that you know has typing noise:

```python
PashtoNormalizer(zwnj="smart")     # removes only ZWNJ with no visible effect; keeps نه‌دی, turns کا‌بل into کابل
PashtoNormalizer(tatweel="smart")  # removes tatweel inside words, standalone tatweel becomes a hyphen
```

## All options

```python
PashtoNormalizer(
    presentation_forms=True,   # fold Arabic presentation forms
    remove_invisible=True,     # ZWSP, ZWJ, LRM/RLM, bidi controls, BOM, soft hyphen
    zwnj="keep",               # "keep" | "smart" | "remove" | "space"
    tatweel="keep",            # "keep" | "smart" | "remove"
    remove_diacritics=True,
    unify_kaf=True,
    unify_alef=True,
    unify_maksura=True,
    unify_heh=True,
    merge_heh_yeh=False,       # ۀ -> ه
    canonicalize_gaf=True,
    urdu_letters=True,
    unify_yeh=None,            # None | "arabic" | "persian" | "all"  (ablation studies only)
    digits="afghan",           # None | "afghan" | "persian" | "arabic" | "latin"
    urdu_full_stop=True,
    collapse_whitespace=True,
    keep_newlines=True,
)
```

`digits="afghan"` folds Arabic-Indic digits (`٠-٩`) to the Persian forms (`۰-۹`) and leaves Latin digits alone. The other values fold every other digit family into the one you name.

`unify_yeh="all"` destroys grammatical information. It exists only so you can measure how much damage over-normalization does.

Save and restore a configuration with `norm.to_dict()` and `PashtoNormalizer.from_dict(...)`.

## Seeing what changed

The normalizer never hides its work. `changes()` returns one entry per altered character, with the span in the **original** text and the name of the rule:

```python
norm = PashtoNormalizer()

original = "پاكستان"
norm.normalize_token(original)      # 'پاکستان'   (the original string is untouched)

for c in norm.changes(original):
    print(c)
# Change(start=2, end=3, original='ك', replacement='ک', rule='arabic-kaf')
```

A spell checker can use this to underline `original[c.start:c.end]` and suggest `c.replacement`, instead of pretending the original never existed. The same information is available from the command line: `pashto-normalizer explain "پاكستان"`.

Rule names: `arabic-kaf`, `gaf`, `urdu-letter`, `alef-variant`, `alef-maksura`, `heh-variant`, `heh-yeh`, `digits`, `urdu-full-stop`, `presentation-form`, `invisible-character`, `diacritic`, `combining-mark`, `whitespace`, `zwnj`, `tatweel`.

## Mapping results back to the original text

Normalization changes lengths. Use the offset-tracking path to trace anything back to the raw text:

```python
norm = PashtoNormalizer()
text = "  كابل   ښار"
out, offsets = norm.normalize_with_offsets(text)    # out == 'کابل ښار'

start = out.index("ښار")
a, b = norm.original_span(offsets, start, start + 3)
text[a:b]                                            # 'ښار'
```

`normalize()` and `normalize_with_offsets()` share one code path, so they always produce the same text. Normalizing twice gives the same result as normalizing once (idempotent).

## Command line

```bash
python -m pashto_normalizer normalize "پاكستان ٢٠٢٦"             # a string
python -m pashto_normalizer normalize -i raw.txt -o clean.txt    # a file, line by line
python -m pashto_normalizer normalize --profile stemmer -i raw.txt -o clean.txt   # profiles: standard | unicode | stemmer
python -m pashto_normalizer explain "پاكستان گل"                   # show every change and its rule
echo "پاكستان" | python -m pashto_normalizer normalize            # from stdin

python -m pashto_normalizer audit -i corpus.txt                  # which characters are in my data?
```

After `pip install .` the same commands are available as `pashto-normalizer`.

## Working with big files

`normalize` and `audit` read the file **line by line**, so memory stays flat for any size. The normalizer processes roughly 1.5 million characters per second on an ordinary CPU, so a corpus of 8 million tokens takes about half a minute.

**Recommended first step for any corpus: run the audit.** It counts every character and flags anything outside the Standard-Pashto inventory, so you see which rules matter for your data.

```text
$ python -m pashto_normalizer audit -i corpus.txt
characters: 65520   distinct: 72   unexpected distinct: 6

char  code          count  meaning
ك     U+0643            15  Arabic kaf (becomes ک)
ـ     U+0640             6  tatweel
```

## Project layout

```text
pashto_normalizer/
├── normalizer.py    Normalizer, profiles, offset tracking
├── audit.py         corpus character audit
├── chars.py         alphabet and digit constants
└── cli.py           command line interface
tests/
└── test_normalizer.py
```

## Roadmap

This repository is the foundation layer. The normalizer is designed to be shared by later components (tokenizer, spell checker, grammar checker, stemmer) that will each answer their own question on top of it.

## Tests

```bash
python -m unittest discover -s tests -v
```

The suite covers each rule, the keep-by-default behavior for ZWNJ and tatweel, the five yeh letters, `changes()`, offset tracking, idempotency on random input for every profile, and the command line.

## Limits

- **It does not fix spelling or grammar.** It will not turn `کړکي` into `کړکې`, `سړي` into `سړی`, or `کا‌بل` into `کابل`; those belong to a spell checker and a grammar checker.
- **It does not add or repair spaces between words.** Only the characters and spacing already in the text are cleaned.
- **Standard Pashto only.** Dialect spellings are left as they are.
- **Rules are tied to the Kabul / Afghan standard.** For example `گ` always becomes `ګ`, and digits go to the Persian forms. Switch options off if your corpus follows another convention.

## Contributing

Issues and pull requests are welcome. Please run the tests before you submit, and add a test for every rule you change.

## License

[MIT](LICENSE)
