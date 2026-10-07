"""Pashto_Normalizer: a normalizer for Standard (Kabul / Afghan) Pashto.

* :class:`PashtoNormalizer` - Unicode clean-up, letter canonicalization, ZWNJ, tatweel,
  digits and whitespace, with offset tracking and three profiles
* :mod:`audit`         - count the characters in a corpus and flag unexpected ones
"""

from . import audit
from .normalizer import Change, PashtoNormalizer

__version__ = "0.2.0"

__all__ = ["PashtoNormalizer", "Change", "audit", "normalize"]


def normalize(text: str, **kwargs) -> str:
    """Normalize ``text`` with the standard profile. Keyword arguments go to :class:`PashtoNormalizer`."""
    return PashtoNormalizer(**kwargs).normalize(text)
