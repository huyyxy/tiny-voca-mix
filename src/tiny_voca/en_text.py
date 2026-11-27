"""English phone inventory and IPA mapping for the Misaki adapter."""
import unicodedata

CONSONANTS = ("p", "b", "t", "d", "k", "ɡ", "f", "v", "θ", "ð", "s", "z", "ʃ", "ʒ", "h",
              "m", "n", "ŋ", "l", "ɹ", "j", "w", "tʃ", "dʒ", "ɾ", "ʔ")
VOWELS = ("ə", "ɐ", "ɚ", "ᵻ", "ɪ", "i", "iː", "ɛ", "æ", "ʌ", "ɑː", "ɔ", "ɔː", "ʊ", "uː", "ɜː",
          "eɪ", "aɪ", "ɔɪ", "oʊ", "aʊ", "iə", "oː",
          "ɑːɹ", "ɔːɹ", "oːɹ", "ɪɹ", "ɛɹ", "ʊɹ", "aɪɚ", "aɪə", "əl", "n̩")
PHONES = CONSONANTS + VOWELS
PHONE_SET = frozenset(PHONES)
VOWEL_SET = frozenset(VOWELS)
STRESS_MARKS = {"ˈ": 1, "ˌ": 2}

# eSpeak phonemes outside the inventory (foreign words, rare allophones) map to
# the closest inventory phone(s). Anything else becomes <unk> and is reported.
FALLBACK = {
    "r": ("ɹ",), "ɻ": ("ɹ",), "ʁ": ("ɹ",), "x": ("k",), "ç": ("h",), "ɬ": ("l",), "ɫ": ("l",), "ɲ": ("n", "j"),
    "ts": ("t", "s"), "dz": ("d", "z"), "β": ("v",), "ɣ": ("ɡ",), "ʎ": ("l", "j"),
    "a": ("æ",), "aː": ("ɑː",), "ɑ": ("ɑː",), "ɒ": ("ɑː",), "ɑ̃": ("ɑː",), "ɔ̃": ("ɔː",), "ɛ̃": ("æ",),
    "e": ("eɪ",), "eː": ("eɪ",), "o": ("oʊ",), "u": ("uː",), "y": ("uː",), "yː": ("uː",),
    "ø": ("ɜː",), "øː": ("ɜː",), "œ": ("ɜː",), "ɜ": ("ɜː",), "ɛː": ("ɛ",), "ɪː": ("ɪ",),
    "əʊ": ("oʊ",), "eə": ("ɛɹ",), "ɪə": ("iə",), "ʊə": ("ʊɹ",), "aʊɚ": ("aʊ", "ɚ"), "l̩": ("əl",), "m̩": ("ə", "m"),
}


def canonical(phone):
    """Map an eSpeak phoneme to inventory phones; ``None`` when unknown."""
    if phone in PHONE_SET:
        return (phone,)
    if phone in FALLBACK:
        return FALLBACK[phone]
    stripped = "".join(c for c in unicodedata.normalize("NFD", phone) if not unicodedata.combining(c))
    for candidate in (stripped, stripped.replace("ː", ""), stripped + "ː"):
        if candidate != phone and candidate in PHONE_SET:
            return (candidate,)
        if candidate != phone and candidate in FALLBACK:
            return FALLBACK[candidate]
    return None
