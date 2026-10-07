"""Character constants for Standard Pashto (Arabic script)."""

# Core Pashto alphabet, including the Pashto-specific letters ټ ډ ړ ږ ښ ڼ ځ څ ې ۍ ګ
# and the five yeh letters ی ي ې ۍ ئ.
PASHTO_ALPHABET = (
    "ا", "آ", "ب", "پ", "ت", "ټ", "ث", "ج", "چ", "ح", "خ", "څ", "ځ",
    "د", "ډ", "ذ", "ر", "ړ", "ز", "ږ", "ژ", "س", "ش", "ښ", "ص", "ض",
    "ط", "ظ", "ع", "غ", "ف", "ق", "ک", "ګ", "ل", "م", "ن", "ڼ", "و",
    "ه", "ۀ", "ی", "ي", "ې", "ۍ", "ئ",
)

# Letters that exist in Pashto but not in Arabic, Persian or Urdu.
PASHTO_SPECIFIC = frozenset("ټډړږښڼځڅۍ")

# Digit families.
LATIN_DIGITS = "0123456789"
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
