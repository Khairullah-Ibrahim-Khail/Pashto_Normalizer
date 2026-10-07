"""Command line interface: ``pashto-normalizer`` or ``python -m pashto_normalizer``."""

from __future__ import annotations

import argparse
import sys
from typing import Iterator, List, Optional

from . import PashtoNormalizer, audit

_PROFILES = {
    "standard": PashtoNormalizer.standard,
    "unicode": PashtoNormalizer.unicode_only,
    "stemmer": PashtoNormalizer.for_stemmer,
}


def _lines(paths: List[str]) -> Iterator[str]:
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                yield line


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pashto-normalizer", description="Standard-Pashto text normalizer"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("normalize", help="normalize text, or a file line by line (any size)")
    p.add_argument("text", nargs="?", help="text to normalize (else --input, else stdin)")
    p.add_argument("-i", "--input", help="UTF-8 input file")
    p.add_argument("-o", "--output", help="output file (default: stdout)")
    p.add_argument(
        "--profile",
        choices=sorted(_PROFILES),
        default="standard",
        help="standard (default), unicode (Unicode layer only, no letter changed) or stemmer (also strips ZWNJ and tatweel)",
    )

    p = sub.add_parser("explain", help="show every change normalization would make to a text")
    p.add_argument("text", help="text to inspect")
    p.add_argument("--profile", choices=sorted(_PROFILES), default="standard")

    p = sub.add_parser("audit", help="count characters in text files and flag unexpected ones")
    p.add_argument("-i", "--input", required=True, nargs="+", help="UTF-8 text file(s)")
    p.add_argument("--top", type=int, default=40, help="rows to show (default 40)")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "audit":
        print(audit.report(audit.char_inventory(_lines(args.input)), top=args.top))
        return 0

    norm = _PROFILES[args.profile]()
    if args.command == "explain":
        found = norm.changes(args.text)
        if not found:
            print("no changes")
        for c in found:
            print(f"{c.start}-{c.end}\t{c.rule}\t{c.original!r} -> {c.replacement!r}")
        return 0

    if args.text:
        print(norm.normalize(args.text))
        return 0

    source = _lines([args.input]) if args.input else sys.stdin
    out = open(args.output, "w", encoding="utf-8", newline="\n") if args.output else sys.stdout
    try:
        for line in source:
            out.write(norm.normalize(line.rstrip("\r\n")).strip() + "\n")
    finally:
        if args.output:
            out.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
