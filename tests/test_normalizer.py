import random
import unittest
from collections import Counter

import contextlib
import io
import os
import tempfile

import pashto_normalizer
from pashto_normalizer import PashtoNormalizer, audit
from pashto_normalizer.cli import main as cli_main

N = PashtoNormalizer()
ZW = "‌"


class UnicodeCleanup(unittest.TestCase):
    def test_zero_width_and_bidi_removed(self):
        self.assertEqual(N("کا\u200bبل"), "کابل")  # ZWSP
        self.assertEqual(N("\ufeffکابل\u200f"), "کابل")  # BOM + RLM
        self.assertEqual(N("کا\u200dبل"), "کابل")  # ZWJ
        self.assertEqual(N("کا\u202bبل\u202c"), "کابل")  # bidi embedding

    def test_presentation_forms_folded(self):
        self.assertEqual(N("ﻛﺎﺑﻠ"), "کابل")

    def test_diacritics_removed(self):
        self.assertEqual(N("مُدَّت"), "مدت")

    def test_diacritics_can_be_kept(self):
        self.assertEqual(PashtoNormalizer(remove_diacritics=False)("مُدَّت"), "مُدَّت")

    def test_madda_kept_hamza_alef_folded(self):
        self.assertEqual(N("آ"), "آ")
        self.assertEqual(N("أ"), "ا")
        self.assertEqual(N("إ"), "ا")
        self.assertEqual(N("أ"), "ا")  # decomposed alef + hamza


class LetterCanonicalization(unittest.TestCase):
    def test_kaf_alef_maksura_heh(self):
        self.assertEqual(N("پاكستان"), "پاکستان")
        self.assertEqual(N("ى"), "ی")
        for ch in "ةہۃھ":
            self.assertEqual(N(ch), "ه", ch)

    def test_gaf_canonicalized(self):
        self.assertEqual(N("گلبهار"), "ګلبهار")
        self.assertEqual(N("ګلبهار"), "ګلبهار")

    def test_urdu_keyboard_letters(self):
        self.assertEqual(N("ٹول ڈاکټر ڑ ے"), "ټول ډاکټر ړ ې")

    def test_five_yeh_forms_survive(self):
        s = "ی ي ې ۍ ئ"
        self.assertEqual(N(s), s)
        for w in ("سړی", "سړي", "ښکلې", "نجلۍ", "کوي", "ئ"):
            self.assertEqual(N(w), w)

    def test_pashto_specific_letters_survive(self):
        s = "ټ ډ ړ ږ ښ څ ځ ګ ڼ ې ۍ"
        self.assertEqual(N(s), s)

    def test_yeh_map_never_contains_a_yeh_by_default(self):
        for y in "يېۍئی":
            self.assertNotIn(ord(y), N._table)

    def test_yeh_ablation_modes(self):
        self.assertEqual(PashtoNormalizer(unify_yeh="arabic")("ی"), "ي")
        self.assertEqual(PashtoNormalizer(unify_yeh="persian")("ي"), "ی")
        self.assertEqual(PashtoNormalizer(unify_yeh="all")("ي ې ۍ ئ"), "ی ی ی ی")

    def test_heh_yeh_kept_and_composed_by_default(self):
        self.assertEqual(N("هغۀ"), "هغۀ")
        self.assertEqual(N("هغهٔ"), "هغۀ")  # decomposed form -> same letter
        self.assertEqual(N("هغهٔ"), N("هغۀ"))

    def test_heh_yeh_merge_option(self):
        m = PashtoNormalizer(merge_heh_yeh=True)
        self.assertEqual(m("هغۀ"), "هغه")
        self.assertEqual(m("هغهٔ"), "هغه")


class ZwnjRules(unittest.TestCase):
    """ZWNJ is a spelling signal, so the default keeps it exactly as written."""

    def test_default_keeps_every_zwnj(self):
        for s in ("نه" + ZW + "دی", "کا" + ZW + "بل", ZW + "کابل" + ZW + ZW, "نه" + ZW + ZW + "دی"):
            self.assertEqual(N(s), s)

    def test_kabul_with_and_without_zwnj_stay_different(self):
        self.assertNotEqual(N("کا" + ZW + "بل"), N("کابل"))

    def test_smart_mode_removes_only_invisible_zwnj(self):
        sm = PashtoNormalizer(zwnj="smart")
        self.assertEqual(sm("نه" + ZW + "دی"), "نه" + ZW + "دی")  # meaningful, kept
        self.assertEqual(sm("له" + ZW + "منځه"), "له" + ZW + "منځه")
        self.assertEqual(sm("کا" + ZW + "بل"), "کابل")  # after a non-joiner
        self.assertEqual(sm(ZW + "کابل" + ZW + ZW), "کابل")  # edges and runs
        self.assertEqual(sm("نه" + ZW + ZW + ZW + "دی"), "نه" + ZW + "دی")
        self.assertEqual(sm("کابل" + ZW + " ښار"), "کابل ښار")
        self.assertEqual(sm("a" + ZW + "b"), "ab")

    def test_remove_and_space_modes(self):
        self.assertEqual(PashtoNormalizer(zwnj="remove")("نه" + ZW + "دی"), "نهدی")
        self.assertEqual(PashtoNormalizer(zwnj="space")("نه" + ZW + "دی"), "نه دی")


class TatweelRules(unittest.TestCase):
    def test_default_keeps_every_tatweel(self):
        for s in ("افغانســـتان", "هند ـ ارام", "كتــاب".replace("ك", "ک"), "ډاکټر ـ احمد"):
            self.assertEqual(N(s), s)

    def test_smart_mode(self):
        sm = PashtoNormalizer(tatweel="smart")
        self.assertEqual(sm("افغانســـتان"), "افغانستان")
        self.assertEqual(sm("هند ـ ارام"), "هند - ارام")

    def test_remove_mode(self):
        self.assertEqual(PashtoNormalizer(tatweel="remove")("هند ـ ارام"), "هند ارام")
        self.assertEqual(PashtoNormalizer(tatweel="remove")("افغانســـتان"), "افغانستان")


class DigitsAndPunctuation(unittest.TestCase):
    def test_afghan_digits_default(self):
        self.assertEqual(N("٢٠٢٦"), "۲۰۲۶")
        self.assertEqual(N("۲۰۲۶"), "۲۰۲۶")
        self.assertEqual(N("2026"), "2026")  # Latin untouched

    def test_other_digit_modes(self):
        self.assertEqual(PashtoNormalizer(digits="latin")("۵٣7"), "537")
        self.assertEqual(PashtoNormalizer(digits="persian")("123"), "۱۲۳")
        self.assertEqual(PashtoNormalizer(digits="arabic")("۱۲"), "١٢")
        self.assertEqual(PashtoNormalizer(digits=None)("٢۲2"), "٢۲2")

    def test_urdu_full_stop(self):
        self.assertEqual(N("سلام۔"), "سلام.")
        self.assertEqual(PashtoNormalizer(urdu_full_stop=False)("سلام۔"), "سلام۔")


class Whitespace(unittest.TestCase):
    def test_newlines_kept(self):
        self.assertEqual(N("لومړی کرښه\n\nدوهمه کرښه"), "لومړی کرښه\n\nدوهمه کرښه")

    def test_horizontal_runs_collapsed(self):
        self.assertEqual(N("  کابل \t  ښار  "), "کابل ښار")
        self.assertEqual(N("کابل\u00a0ښار"), "کابل ښار")
        self.assertEqual(N("کابل ښار"), "کابل ښار")

    def test_line_edges_trimmed_and_blank_lines_limited(self):
        self.assertEqual(N("الف \n ب\n\n\n\nج"), "الف\nب\n\nج")
        self.assertEqual(N("الف\r\nب"), "الف\nب")

    def test_keep_newlines_false(self):
        self.assertEqual(PashtoNormalizer(keep_newlines=False)("الف\n\nب"), "الف ب")


class Profiles(unittest.TestCase):
    def test_unicode_layer_changes_no_letter(self):
        m = PashtoNormalizer.unicode_only()
        s = "پاكستان گل ٹ ۀ ٢ مُدَّت سلام۔"
        self.assertEqual(m(s), s)
        self.assertEqual(m("کا\u200bبل"), "کابل")  # invisible character
        # presentation forms become ordinary letters; the kaf stays Arabic kaf in this layer
        self.assertEqual(m("\ufedb\ufe8e\ufe91\ufee0"), "كابل")

    def test_original_is_never_modified(self):
        original = "پاكستان"
        N.normalize_token(original)
        self.assertEqual(original, "پاكستان")
        self.assertEqual(N.normalize_token(original), "پاکستان")

    def test_stemmer_profile_strips_zwnj_and_tatweel(self):
        s = PashtoNormalizer.for_stemmer()
        self.assertEqual(s("نه" + ZW + "دی"), "نهدی")
        self.assertEqual(s("هند ـ ارام"), "هند ارام")

    def test_validation(self):
        for kw in ({"zwnj": "x"}, {"tatweel": "x"}, {"unify_yeh": "x"}, {"digits": "x"}):
            with self.assertRaises(ValueError):
                PashtoNormalizer(**kw)

    def test_config_roundtrip_and_unknown_keys_ignored(self):
        n = PashtoNormalizer(unify_yeh="arabic", digits="latin", zwnj="space")
        self.assertEqual(PashtoNormalizer.from_dict(n.to_dict()).to_dict(), n.to_dict())
        d = n.to_dict()
        d["removed_in_future"] = 1
        self.assertEqual(PashtoNormalizer.from_dict(d).to_dict(), n.to_dict())

    def test_is_normalized(self):
        self.assertTrue(N.is_normalized("پاکستان"))
        self.assertFalse(N.is_normalized("پاكستان"))
        self.assertFalse(N.is_normalized("گلبهار"))


class OffsetsAndRobustness(unittest.TestCase):
    ALPHABET = list("کاب ل\n\t ـ‌\u200b۔گٹۀهَٔ٢۲ ی ي ې ۍ ئ .,") + ["ﻛ", "ﺎ", "ك", "أ"]

    def test_offsets_point_to_source_characters(self):
        text = "كا\u200bبل  ـ  نه‌دی گل"
        out, idx = N.normalize_with_offsets(text)
        self.assertEqual(out, N(text))
        self.assertEqual(len(idx), len(out))
        self.assertEqual(idx, sorted(idx))  # monotonic
        for i, ch in enumerate(out):
            if ch in "بلنده":  # untouched letters map to themselves
                self.assertEqual(text[idx[i]], ch)

    def test_original_span(self):
        text = "  کابل   ښار"
        out, idx = N.normalize_with_offsets(text)
        s = out.index("ښار")
        a, b = N.original_span(idx, s, s + 3)
        self.assertEqual(text[a:b], "ښار")

    def test_fast_and_offset_paths_agree_and_are_idempotent(self):
        rnd = random.Random(7)
        for _ in range(3000):
            s = "".join(rnd.choice(self.ALPHABET) for _ in range(rnd.randint(0, 25)))
            out = N(s)
            self.assertEqual(out, N.normalize_with_offsets(s)[0], repr(s))
            self.assertEqual(N(out), out, repr(s))

    def test_fuzz_other_profiles(self):
        rnd = random.Random(11)
        norms = [
            PashtoNormalizer(zwnj="smart", tatweel="smart"),
            PashtoNormalizer.for_stemmer(),
            PashtoNormalizer.unicode_only(),
            PashtoNormalizer(keep_newlines=False, merge_heh_yeh=True),
        ]
        for _ in range(1500):
            s = "".join(rnd.choice(self.ALPHABET) for _ in range(rnd.randint(0, 25)))
            for n in norms:
                out = n(s)
                self.assertEqual(out, n.normalize_with_offsets(s)[0], repr(s))
                self.assertEqual(n(out), out, repr(s))

    def test_empty(self):
        self.assertEqual(N(""), "")
        self.assertEqual(N.normalize_with_offsets(""), ("", []))


class Changes(unittest.TestCase):
    """The spell checker needs to see what changed, not just the result."""

    def test_reports_substitution_with_span_and_rule(self):
        text = "د پاكستان"
        found = N.changes(text)
        self.assertEqual(len(found), 1)
        c = found[0]
        self.assertEqual((c.original, c.replacement, c.rule), ("ك", "ک", "arabic-kaf"))
        self.assertEqual(text[c.start:c.end], "ك")

    def test_unchanged_text_has_no_changes(self):
        self.assertEqual(N.changes("پاکستان نه" + ZW + "دی هند ـ ارام"), [])

    def test_several_rules(self):
        rules = {c.rule for c in N.changes("گل ٹول سلام۔ ٢ \u200b")}
        self.assertTrue({"gaf", "urdu-letter", "urdu-full-stop", "digits", "invisible-character"} <= rules)

    def test_deletions_are_merged_and_named(self):
        found = PashtoNormalizer(tatweel="remove").changes("افغانســـتان")
        self.assertEqual([(c.rule, c.original, c.replacement) for c in found], [("tatweel", "ـ" * 3, "")])

    def test_changes_agree_with_normalize(self):
        text = "پاكستان\u200bګل٢ٹول" + "گ" + "مُدَّت\ufedb"
        rebuilt = text
        for c in reversed(N.changes(text)):
            rebuilt = rebuilt[: c.start] + c.replacement + rebuilt[c.end:]
        self.assertEqual(rebuilt, N(text))

    def test_cli_explain(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli_main(["explain", "پاكستان"])
        self.assertIn("arabic-kaf", buf.getvalue())
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli_main(["explain", "پاکستان"])
        self.assertEqual(buf.getvalue().strip(), "no changes")


class Audit(unittest.TestCase):
    def test_inventory_and_unexpected(self):
        counts = audit.char_inventory(["کابل ښار\n", "پاكستان ٹ\u200b\n"])
        bad = dict(audit.unexpected(counts))
        self.assertIn("ك", bad)
        self.assertIn("ٹ", bad)
        self.assertIn("\u200b", bad)
        self.assertNotIn("ښ", bad)
        self.assertNotIn("‌", bad)
        self.assertIsInstance(counts, Counter)

    def test_report_text(self):
        text = audit.report(audit.char_inventory(["پاكستان\n"]))
        self.assertIn("U+0643", text)
        self.assertIn("Arabic kaf", text)
        self.assertIn("no unexpected", audit.report(audit.char_inventory(["کابل\n"])))


class Cli(unittest.TestCase):
    def run_cli(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli_main(list(argv))
        return code, buf.getvalue()

    def test_normalize_text_argument(self):
        code, out = self.run_cli("normalize", "پاكستان گل")
        self.assertEqual((code, out), (0, "پاکستان ګل\n"))

    def test_normalize_file_streams_lines(self):
        with tempfile.TemporaryDirectory() as d:
            src, dst = os.path.join(d, "a.txt"), os.path.join(d, "b.txt")
            with open(src, "w", encoding="utf-8") as fh:
                fh.write("پاكستان\r\n\nكابل  ښار\n")
            self.run_cli("normalize", "-i", src, "-o", dst)
            with open(dst, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "پاکستان\n\nکابل ښار\n")

    def test_profiles(self):
        _, out = self.run_cli("normalize", "--profile", "stemmer", "نه" + ZW + "دی")
        self.assertEqual(out, "نهدی\n")

    def test_audit_command(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "a.txt")
            with open(src, "w", encoding="utf-8") as fh:
                fh.write("پاكستان\n")
            _, out = self.run_cli("audit", "-i", src)
            self.assertIn("U+0643", out)

    def test_top_level_helper_and_version(self):
        self.assertEqual(pashto_normalizer.normalize("پاكستان"), "پاکستان")
        self.assertTrue(pashto_normalizer.__version__)


if __name__ == "__main__":
    unittest.main()
