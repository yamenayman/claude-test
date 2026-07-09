from __future__ import annotations

import re


ARABIC_VARIANTS = str.maketrans(
    {
        "أ": "ا",  # أ -> ا
        "إ": "ا",  # إ -> ا
        "آ": "ا",  # آ -> ا
        "ى": "ي",  # ى -> ي
        "ة": "ه",  # ة -> ه
        "ؤ": "و",  # ؤ -> و
        "ئ": "ي",  # ئ -> ي
    }
)
ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
DIACRITICS_RE = re.compile(r"[ً-ٰٟ]")
WHITESPACE_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[\w؀-ۿ]+", flags=re.UNICODE)
STOPWORDS = {
    "في",
    "من",
    "على",
    "عن",
    "الى",
    "إلى",
    "هل",
    "ما",
    "هو",
    "هي",
    "او",
    "أو",
    "لا",
    "اذا",
    "إذا",
    "ذلك",
    "هذا",
    "هذه",
}


def normalize_arabic_text(text: str) -> str:
    text = (text or "").strip().translate(ARABIC_VARIANTS).translate(ARABIC_INDIC_DIGITS)
    text = DIACRITICS_RE.sub("", text)
    return WHITESPACE_RE.sub(" ", text)


def tokenize_for_overlap(text: str) -> set[str]:
    normalized = normalize_arabic_text(text)
    return {token for token in TOKEN_RE.findall(normalized) if len(token) > 1 and token not in STOPWORDS}
