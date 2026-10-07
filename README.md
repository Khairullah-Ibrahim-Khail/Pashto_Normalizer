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

Pashto text on the web is messy. The same word appears with Arabic, Persian or Urdu letters, hidden zero-width characters, PDF presentation forms, stray ZWNJ and tatweel, and inconsistent spacing. Any later step (tokenizing, stemming, training a model) inherits that noise.

Pashto_Normalizer cleans it in one deterministic, local step. It is **conservative for Pashto**: it removes encoding noise but never destroys information that Pashto grammar depends on, such as the five yeh letters.

## Contents

- [Install](#install)
- [Quick start](#quick-start)
- [What it does](#what-it-does)
- [What is never changed](#what-is-never-changed)
- [Profiles](#profiles)
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
from pashto_normalizer import Normalizer

norm = Normalizer()

norm("پاكستان ٢٠٢٦")            # Arabic kaf, Arabic-Indic digits
# 'پاکستان ۲۰۲۶'

norm("گلبهار ٹول")              # Persian gaf, Urdu keyboard letter
# 'ګلبهار ټول'

norm("هند ـ ارام")              # standalone tatweel
# 'هند - ارام'
```

One-liner for single calls:

```python
import pashto_normalizer
pashto_normalizer.normalize("پاكستان")   # 'پاکستان'
```

## What it does

| Input | Output | Rule |
|---|---|---|
| `پاكستان` | `پاکستان` | Arabic kaf `ك` to `ک` |
| `گلبهار` | `ګلبهار` | Persian gaf `گ` to Pashto `ګ` |
| `ٹول ڈاکټر` | `ټول ډاکټر` | Urdu keyboard letters `ٹ ڈ ڑ ے` to `ټ ډ ړ ې` |
| `أ إ ٱ` | `ا` | Alef variants to bare alef (madda `آ` is kept) |
| `ى` `ة ہ ھ` | `ی` `ه` | Alef maksura and heh variants |
| `کا‌بل` (ZWNJ after `ا`) | `کابل` | ZWNJ with no visible effect is removed |
| `نه‌دی` (ZWNJ after `ه`) | `نه‌دی` | Meaningful ZWNJ is **kept** |
| `افغانســـتان` | `افغانستان` | Tatweel inside a word is removed |
| `هند ـ ارام` | `هند - ارام` | A standalone tatweel becomes a hyphen |
| `٢٠٢٦` | `۲۰۲۶` | Arabic-Indic digits to the Afghan (Persian) forms |
| `سلام۔` | `سلام.` | Urdu full stop to the dot |
| `ﻛﺎﺑﻠ` (PDF form) | `کابل` | Arabic presentation forms folded |
| `کابل` with hidden ZWSP / BOM / RLM inside | `کابل` | Invisible and bidi characters removed |
| `مُدَّت` | `مدت` | Diacritics removed |
| `کابل` + no-break space + `ښار` | `کابل ښار` | No-break and thin spaces collapse; **line breaks are kept** |

### Why ZWNJ is handled this way

A ZWNJ only matters when it separates two letters that would otherwise connect, as in `نه‌دی` (`ه` joins forward). After a letter that never joins forward (`ا د ډ ر ړ ز ږ ژ و`) it has no visible effect, so `کا‌بل` and `کابل` would become two different strings for the same word. The normalizer removes those, along with ZWNJ at word edges and repeated ZWNJ, and keeps the rest.

## What is never changed

- The five yeh letters `ی ي ې ۍ ئ` stay distinct. They carry gender, number and case (`سړی` / `سړي` / `ښکلې` / `نجلۍ`).
- Pashto-specific consonants `ټ ډ ړ ږ ښ څ ځ ګ ڼ` are never folded to look-alike Arabic or Persian letters.
- `ۀ` is kept, and its decomposed form (`ه` + hamza mark) is composed to the same `ۀ`. Merge it with `merge_heh_yeh=True` once your corpus counts show it is safe.
- Latin digits and Latin text are left alone.
- Spelling is not corrected (see [Limits](#limits)).

## Profiles

```python
Normalizer.standard()      # default: everything in the table above
Normalizer.minimal()       # Unicode and layout clean-up only, no letter is changed
Normalizer.for_stemmer()   # standard + ZWNJ and tatweel removed (use on single words, after splitting)
```

If you tokenize text, use the standard or minimal profile **before** tokenizing so meaningful ZWNJ is still visible, then use the stemmer profile on each word.

## All options

```python
Normalizer(
    presentation_forms=True,   # fold Arabic presentation forms
    remove_invisible=True,     # ZWSP, ZWJ, LRM/RLM, bidi controls, BOM, soft hyphen
    zwnj="smart",              # "smart" | "keep" | "remove" | "space"
    tatweel="smart",           # "smart" | "keep" | "remove"
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

Save and restore a configuration with `norm.to_dict()` and `Normalizer.from_dict(...)`.

## Mapping results back to the original text

Normalization changes lengths. Use the offset-tracking path to trace anything back to the raw text:

```python
norm = Normalizer()
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
python -m pashto_normalizer normalize --profile stemmer -i raw.txt -o clean.txt
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

## Tests

```bash
python -m unittest discover -s tests -v
```

The suite covers each rule, ZWNJ and tatweel edge cases, the five yeh letters, offset tracking, idempotency on random input, and the command line.

## Limits

- **It does not fix spelling.** For example it cannot know that `کړکي` should be `کړکې`; that needs a lexicon or a model.
- **It does not add or repair spaces between words.** Only the characters and spacing already in the text are cleaned.
- **Standard Pashto only.** Dialect spellings are left as they are.
- **Rules are tied to the Kabul / Afghan standard.** For example `گ` always becomes `ګ`, and digits go to the Persian forms. Switch options off if your corpus follows another convention.

## Contributing

Issues and pull requests are welcome. Please run the tests before you submit, and add a test for every rule you change.

## License

[MIT](LICENSE)
