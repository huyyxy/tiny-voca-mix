"""Kokoro v1.1 Mandarin and American English readings in tiny-voca's inventory."""
import hashlib
import re
import unicodedata
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path

from . import context_en, en_text as en, zh_text as zh

LANGUAGE = "mixed"
DEFAULT_SPEAKERS = ("male", "female")
FRONTEND = "misaki-v1.1-zh-us"
NothingToPronounce = zh.NothingToPronounce
SYMBOLS = zh.SPECIALS + zh.PUNCTUATION + tuple("zh/"+p for p in zh.PHONES) + tuple("en/"+p for p in en.PHONES)
SYMBOL_TO_ID = {p:i for i,p in enumerate(SYMBOLS)}
PHONE_IDS = {i for i,p in enumerate(SYMBOLS) if "/" in p}
VOWELS = tuple("zh/"+p for p in zh.VOWELS) + tuple("en/"+p for p in en.VOWELS)
_HAN = r"[\u3400-\u9fff]"
_ZERO_SPELLING = {v: k for k, (_, v) in zh._Y_W.items()}
_MISAKI_EN = {"A":"eɪ", "I":"aɪ", "O":"oʊ", "W":"aʊ", "Y":"ɔɪ", "T":"ɾ",
              "ʧ":"tʃ", "ʤ":"dʒ", "ᵊ":"ə", "ɜ":"ɜː", "ɑ":"ɑː", "u":"uː"}
_PACKAGES = ("misaki", "jieba", "pypinyin", "pypinyin-dict", "spacy", "en-core-web-sm",
             "phonemizer-fork", "espeakng-loader", "num2words", "regex")


def frontend_identity():
    return dict(phonemizer=FRONTEND, symbols=list(SYMBOLS))


@lru_cache()
def frontend_fingerprint():
    digest = hashlib.sha256()
    for module in (__file__, zh.__file__, en.__file__, context_en.__file__):
        digest.update(Path(module).read_bytes())
    for package in _PACKAGES:
        digest.update(f"{package}={version(package)}\n".encode())
    return digest.hexdigest()


@lru_cache()
def _mandarin():
    from misaki.zh_frontend import ZHFrontend
    return ZHFrontend()


@lru_cache()
def _american():
    from misaki import en as misaki_en, espeak
    return misaki_en.G2P(british=False, trf=False, fallback=espeak.EspeakFallback(british=False))


def _zh_unit(initial, final):
    tone = final[-1:]
    if tone not in ("1", "2", "3", "4", "5"):
        raise ValueError(f"Unmapped Misaki syllable: {initial}{final}")
    body = final[:-1]
    rhotic = body.endswith("R")
    if rhotic:
        body = body[:-1]
    body = {"ii":"i", "iii":"i", "n":"en", "ng":"eng"}.get(body, body)
    body = zh._FINAL_ALIASES.get(body, body)
    if body not in zh.FINALS or (initial and initial not in zh.INITIALS):
        raise ValueError(f"Unmapped Misaki syllable: {initial}{final}")
    if initial:
        spelling = initial + (body.replace("v", "u") if initial in ("j","q","x") else body)
    else:
        spelling = _ZERO_SPELLING.get(body, body)
    phones = ([initial] if initial else []) + [body + tone]
    if rhotic:
        spelling += "r"
        phones.append("r")
    return spelling.replace("v", "u"), [("zh/" + p, 0) for p in phones]


def _reading_overrides(part):
    readings = {}
    for word, reading in zh._NEUTRAL_WORDS.items():
        for match in re.finditer(word, part):
            readings[match.end()-1] = reading
    for pattern, reading in zh._READING_RULES:
        for match in pattern.finditer(part):
            readings[match.start(1)] = reading
    for pattern, reading in [(r"本(地)|热带(地)(?=区)", "di4"),
                             (r"大(都)(?=会)", "du1"),
                             (r"东(西)(?=方向)", "xi1")]:
        for match in re.finditer(pattern, part):
            readings[match.start(match.lastindex)] = reading
    for index in zh.fixed_one_positions(part):
        readings[index] = "yi1"
    return readings


def _mandarin_units(part):
    # Read Misaki's syllables immediately before it packs them into Kokoro's
    # character vocabulary. MMS needs the individual syllable boundaries.
    from jieba import posseg
    frontend = _mandarin()
    words = frontend.tone_modifier.pre_merge_for_modify(posseg.lcut(part))
    overrides = _reading_overrides(part)
    offset = 0
    lexical_tones = []
    prepared = []
    for word, pos in words:
        initials, finals = frontend._get_initials_finals(word)
        for i in range(len(word)):
            reading = overrides.get(offset + i)
            if reading:
                initial, body, tone = zh.split_pinyin(reading)
                initials[i], finals[i] = initial, body + str(tone)
        lexical_tones.extend(final[-1:] for final in finals)
        prepared.append((offset, word, pos, initials, finals))
        offset += len(word)

    for offset, word, pos, initials, finals in prepared:
        finals = frontend.tone_modifier.modified_tone(word, pos, finals)
        for i in range(len(word)):
            at = offset + i
            if at in overrides:
                # Preserve reviewed readings against broad suffix/neutral-tone
                # heuristics (e.g. 地 in 本地) and preserve fixed numeral 一.
                finals[i] = finals[i][:-1] + lexical_tones[at]
            if (lexical_tones[at:at+2] == ["3", "3"]
                    and (at in overrides or at+1 in overrides)):
                # Corrections can create a third-tone pair across jieba words:
                # 我们得 | 赶紧. Either member may be the corrected syllable.
                finals[i] = finals[i][:-1] + "2"
        initials, finals = frontend._merge_erhua(initials, finals, word, pos)
        for initial, final in zip(initials, finals, strict=True):
            yield _zh_unit(initial, final)


def _punctuation(char):
    char = char.translate(zh._QUOTES)
    if char in zh.PUNCTUATION:
        return "", [(char, 0)]
    return None


def _english_units(part):
    _, tokens = _american()(part)
    for token in tokens:
        if not token.phonemes:
            if re.search("[A-Za-z]", token.text):
                raise ValueError(f"Missing Misaki reading for {token.text!r}")
            continue
        phones = []
        stress = 0
        for char in token.phonemes:
            if char in en.STRESS_MARKS:
                stress = en.STRESS_MARKS[char]
                continue
            if char.isspace():
                continue
            punctuation = _punctuation(char)
            if punctuation:
                yield punctuation
                continue
            mapped = en.canonical(_MISAKI_EN.get(char, char))
            if mapped is None:
                raise ValueError(f"Unknown Misaki phone {char!r} in {token.text!r}")
            for phone in mapped:
                vowel = phone in en.VOWEL_SET
                phones.append(("en/" + phone, stress if vowel else 0))
                if vowel:
                    stress = 0
        if phones:
            spelling = re.sub("[^a-z]", "", token.text.lower())
            if not spelling:
                raise ValueError(f"Missing alignment spelling for {token.text!r}")
            yield spelling, phones


def _english_context(part, start, overrides):
    # Split only at reviewed heteronyms; keep other English spans intact for
    # Misaki's part-of-speech analysis.
    cursor = 0
    for token in re.finditer(r"[A-Za-z]+(?:'[A-Za-z]+)*", part):
        phones = overrides.get(start + token.start())
        if phones is not None:
            if part[cursor:token.start()].strip():
                yield from _english_units(part[cursor:token.start()])
            yield token.group().lower(), phones
            cursor = token.end()
    if part[cursor:].strip():
        yield from _english_units(part[cursor:])


def units(text):
    """Return romanized MMS units with the precise acoustic tokens each owns."""
    from num2words import num2words
    text = unicodedata.normalize("NFKC", text).translate(zh._QUOTES)
    if re.search(_HAN, text):
        text = zh.normalize_text(re.sub(r"[-−](?=\d)", "负", text))
    else:
        text = re.sub(r"-?\d+(?:\.\d+)?", lambda m:num2words(m.group()), text)
    result = [("", [(zh.BOS, 0)])]
    overrides = context_en.context_phones(text)
    for match in re.finditer(_HAN + r"+|[^\u3400-\u9fff]+", text):
        part = match.group()
        if not part.strip():
            continue
        if re.match(_HAN, part):
            result.extend(_mandarin_units(part))
        elif re.search("[A-Za-z]", part):
            for word, phones in _english_context(part, match.start(), overrides):
                if word and result[-1][0]:
                    result.append(("", [(zh.SP, 0)]))
                result.append((word, phones))
        else:
            result.extend(p for c in part if (p := _punctuation(c)))
    if not any(word for word, _ in result):
        raise NothingToPronounce(text)
    return result + [("", [(zh.EOS, 0)])]


def phonemize(text):
    pairs = [pair for _, phones in units(text) for pair in phones]
    symbols, stress = zip(*pairs)
    return zh.Phonemized(symbols, tuple(SYMBOL_TO_ID[s] for s in symbols), stress, ())
