"""Mandarin front end: Chinese text -> initial / final tokens carrying tone.

This mirrors ``en_text`` so the rest of the system (annotation, training,
inference) does not need to know which language it is running. Select it with
``TINY_VOCA_LANG=zh``.

Design decisions that differ from English, and why:

* **Tone lives inside the token.** A final is written ``<final><tone>``, for
  example ``a1``, ``ong2``, ``i4``, ``er5`` (5 = neutral). English keeps stress
  as a parallel feature because it is prosodic; Mandarin tone is lexical, it is
  given by the text and must reach the encoder as part of the symbol. It also
  means one token = one phone = one alignment label, which is what the
  duration layer needs.
* **No word-boundary token.** Mandarin is written without spaces. Punctuation
  carries the pauses; the model sees syllable adjacency directly.
* **Initials are separate tokens.** Consonants are short but acoustically
  distinct, and splitting them off keeps the final inventory at 35 instead of
  a few hundred whole syllables.
* **Tone sandhi is applied to the text before tokenisation**, because the audio
  we generate from that text already exhibits the sandhi: a third tone followed
  by a third tone is spoken as second + third, so it must be annotated that way.

Symbol inventory (append-only; changing it invalidates checkpoints):

    specials (5) + punctuation (12) + initials (21) + finals x 5 tones (175)
"""

from dataclasses import dataclass
import hashlib
import json
import re
import unicodedata

FRONTEND_VERSION = 1
LANGUAGE = "zh"
DEFAULT_SPEAKERS = ("ZH_F1", "ZH_M1")
# Interface parity with en_text: infer.py reads these to decide which front end
# a checkpoint wants and how the user selects one.
FRONTENDS = ("pinyin",)
FRONTEND_VARIABLE = "TINY_VOCA_LANG"

PAD, BOS, EOS, SP, UNK = "<pad>", "<bos>", "<eos>", "<sp>", "<unk>"
SPECIALS = (PAD, BOS, EOS, SP, UNK)
PUNCTUATION = (",", ".", "?", "!", ";", ":", '"', "'", "(", ")", "—", "…")

INITIALS = ("b", "p", "m", "f", "d", "t", "n", "l", "g", "k", "h",
            "j", "q", "x", "zh", "ch", "sh", "r", "z", "c", "s")
FINALS = ("a", "o", "e", "ai", "ei", "ao", "ou", "an", "en", "ang", "eng", "ong", "er",
          "i", "ia", "ie", "iao", "iu", "ian", "in", "iang", "ing", "iong",
          "u", "ua", "uo", "uai", "ui", "uan", "un", "uang", "ueng",
          "v", "ve", "van", "vn")
TONES = (1, 2, 3, 4, 5)
FINAL_TOKENS = tuple(final + str(tone) for final in FINALS for tone in TONES)
PHONES = INITIALS + FINAL_TOKENS
SYMBOLS = SPECIALS + PUNCTUATION + PHONES
SYMBOL_TO_ID = {symbol: index for index, symbol in enumerate(SYMBOLS)}
PHONE_SET = frozenset(PHONES)
PHONE_IDS = frozenset(SYMBOL_TO_ID[p] for p in PHONES)

# Finals are voiced by definition; the model uses this set to keep vowel frames
# voiced when the pitch tracker drops creaky ones.
VOWELS = FINAL_TOKENS
VOWEL_SET = frozenset(VOWELS)
# Unaspirated stops, aspirated stops, fricatives and affricates: the QC probe
# in the annotation layer uses this to check pitch-tracker voicing flips.
VOICELESS = frozenset(("b", "p", "d", "t", "g", "k", "f", "h",
                       "j", "q", "x", "zh", "ch", "sh", "z", "c", "s"))
VOICED_INITIALS = frozenset(("m", "n", "l", "r"))

# pinyin is written without the umlaut after these initials: ju, que, xuan, yun
_UMLAUT_INITIALS = frozenset(("j", "q", "x"))
# Syllables written with y/w are phonologically zero-initial.
_Y_W = {
    "yi": ("", "i"), "ya": ("", "ia"), "ye": ("", "ie"), "yao": ("", "iao"),
    "you": ("", "iu"), "yan": ("", "ian"), "yin": ("", "in"), "yang": ("", "iang"),
    "ying": ("", "ing"), "yong": ("", "iong"), "yo": ("", "io"),
    "yu": ("", "v"), "yue": ("", "ve"), "yuan": ("", "van"), "yun": ("", "vn"),
    "wu": ("", "u"), "wa": ("", "ua"), "wo": ("", "uo"), "wai": ("", "uai"),
    "wei": ("", "ui"), "wan": ("", "uan"), "wen": ("", "un"), "wang": ("", "uang"),
    "weng": ("", "ueng"),
}
# pinyin spelling variants that map onto one inventory final
_FINAL_ALIASES = {"iou": "iu", "uei": "ui", "uen": "un", "ü": "v", "üe": "ve", "üan": "van", "ün": "vn"}

_QUOTES = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "`": "'", "´": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"', "«": '"', "»": '"',
    "–": "—", "―": "—", "－": "—", "〜": "—",
    "［": "(", "｛": "(", "【": "(", "《": "(", "「": "(", "『": "(",
    "］": ")", "｝": ")", "】": ")", "》": ")", "」": ")", "』": ")",
})
# Chinese punctuation folded onto the ASCII inventory above.
_PUNCTUATION_FOLD = {
    "，": ",", "。": ".", "！": "!", "？": "?", "；": ";", "：": ":",
    "、": ",", "．": ".", "·": "—", "～": "—", "　": " ",
}
_PUNCTUATION_CHARS = frozenset(PUNCTUATION)
_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_LATIN_RUN = re.compile(r"[A-Za-z]+")

_DIGITS = "零一二三四五六七八九"
_SMALL_UNITS = ("", "十", "百", "千")
_BIG_UNITS = ("", "万", "亿")


class NothingToPronounce(ValueError):
    """The text has no syllable to say: only marks, emoji and the like."""


@dataclass(frozen=True)
class Phonemized:
    symbols: tuple
    ids: tuple
    stress: tuple
    unknown: tuple

    def __len__(self):
        return len(self.ids)


@dataclass(frozen=True)
class Syllable:
    initial: str
    final: str
    tone: int
    char: str


def _pypinyin():
    try:
        import pypinyin
    except ImportError as error:
        raise RuntimeError('the Mandarin front end needs pypinyin: pip install pypinyin') from error
    return pypinyin


def frontend():
    return "pinyin"


def set_frontend(name):
    """Kept for interface parity with the English front end; zh has one path."""
    if name not in ("pinyin", "own", "espeak"):
        raise ValueError(f"unknown front end {name!r}")


def frontend_identity():
    return {"frontend_version": FRONTEND_VERSION, "language": LANGUAGE,
            "phonemizer": "pypinyin", "style": "TONE3", "symbols": list(SYMBOLS)}


def frontend_runtime():
    return {"pypinyin_version": _pypinyin().__version__}


def frontend_fingerprint():
    return hashlib.sha256(json.dumps(frontend_identity(), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


# --------------------------------------------------------------------------
# text normalization
# --------------------------------------------------------------------------

def _int_to_chinese(value):
    """Read an integer the way Mandarin does, e.g. 2026 -> 两千零二十六."""
    if value == 0:
        return _DIGITS[0]
    if value < 0:
        return "负" + _int_to_chinese(-value)
    groups, rest = [], value
    while rest:
        groups.append(rest % 10000)
        rest //= 10000
    parts = []
    for power in range(len(groups) - 1, -1, -1):
        group = groups[power]
        if not group:
            continue
        text = ""
        zero = False
        for index in range(3, -1, -1):
            digit = (group // 10 ** index) % 10
            if digit == 0:
                zero = bool(text)
                continue
            if zero:
                text += _DIGITS[0]
                zero = False
            text += _DIGITS[digit] + _SMALL_UNITS[index]
        parts.append(text + _BIG_UNITS[power])
    result = _DIGITS[0].join(parts) if len(parts) > 1 and groups[0] and len(str(groups[-1])) < 4 else "".join(parts)
    # 10-19 are read "十..." and never "一十..."
    if result.startswith("一十"):
        result = result[1:]
    return result


def _digit_by_digit(digits):
    return "".join(_DIGITS[int(d)] for d in digits)


def _read_decimal(number):
    whole, _, fraction = number.partition(".")
    text = _int_to_chinese(int(whole)) if whole else _DIGITS[0]
    return text + "点" + _digit_by_digit(fraction) if fraction else text


def normalize_text(text):
    """Fold full-width forms, Chinese punctuation and numbers into the
    inventory. Numbers become the characters a speaker would actually say, so
    the front end never has to read digits."""
    text = unicodedata.normalize("NFKC", text).translate(_QUOTES)
    text = "".join(_PUNCTUATION_FOLD.get(char, char) for char in text)
    text = re.sub(r"\.{3,}", "…", text)
    text = re.sub(r"-{2,}|\s-\s", "—", text)
    # percentages before plain numbers
    text = re.sub(r"(\d+(?:\.\d+)?)\s*%", lambda m: "百分之" + _read_decimal(m.group(1)), text)
    # years read digit by digit
    text = re.sub(r"(\d{4})\s*年", lambda m: _digit_by_digit(m.group(1)) + "年", text)
    # decimals
    text = re.sub(r"\d+\.\d+", lambda m: _read_decimal(m.group(0)), text)
    # Long digit runs (phone numbers, IDs, account numbers) are read one digit
    # at a time; reading 13812345678 as a cardinal number would be absurd.
    text = re.sub(r"\d{7,}", lambda m: _digit_by_digit(m.group(0)), text)
    # remaining integers
    text = re.sub(r"\d+", lambda m: _int_to_chinese(int(m.group(0))), text)
    return re.sub(r"\s+", " ", text).strip()


# --------------------------------------------------------------------------
# pinyin -> (initial, final, tone)
# --------------------------------------------------------------------------

def split_pinyin(syllable):
    """Split one TONE3 syllable such as ``zhong1`` or ``lv4``.

    Returns ``None`` when the final is outside the inventory, which the caller
    reports as an unknown symbol rather than silently mangling it.
    """
    tone = 5
    body = syllable.replace("ü", "v")
    if body and body[-1].isdigit():
        tone, body = int(body[-1]), body[:-1]
    if not 1 <= tone <= 5:
        return None
    if body in _Y_W:
        initial, final = _Y_W[body]
    else:
        initial = ""
        for candidate in ("zh", "ch", "sh"):
            if body.startswith(candidate):
                initial = candidate
                break
        if not initial and body[:1] in tuple(i for i in INITIALS if len(i) == 1):
            initial = body[0]
        final = body[len(initial):]
        if initial in _UMLAUT_INITIALS and final.startswith("u"):
            final = "v" + final[1:]
    final = _FINAL_ALIASES.get(final, final)
    if final not in FINALS:
        return None
    return initial, final, tone


# One capturing group locates the character whose lexical reading changes.
# Keep homographs local: 大都市/大都会, 地方政府 and 东西方向 carry other readings.
_CONTEXT_READINGS = {
    'chang2': r'(?:很|挺|稍|这么|那么|有点)(长)(?=的|一点|时间|$)',
    'dou1': r'(?:大家|我们|他们|通常|一切|家长|事情|手上|全世界|每周|每天|每星期|什么|的是|其实是|就是|啊)(都)(?=会)',
    'wei2': r'华(为)(?=的|是|有|包括|对|他|$)',
    'jiao1': r'(教)(?=他们|他怎么|大家|我)',
    'dei3': r'我们(得)(?=抓紧|提前|先把|赶紧|想个|找个|从长计议)',
    'tiao2': r'(调)(?=成静音|理自我)',
    'zhi1': r'这(只)(?=小狗)',
    'zhong4': r'(种)(?=满了梧桐树)',
    'shu3': r'(数)(?=了一遍人数|着路边的电线杆)',
    'hang2': r'投(行)(?=啊|业界|的|$)',
    'dai1': r'(待)(?=在他们|在$)',
    'la4': r'手机(落)(?=在出租车)',
    'za1': r'头发(扎)(?=起来)',
    'tan2': r'(弹)(?=出来)',
    'zheng4': r'(挣)(?=很多呀)',
    'jia4': r'请这个(假)',
    'hai2': r'男生(还)(?=是女生)',
    'shao3': r'人很(少)(?=相当于)',
    'kong4': r'(空)(?=两格)',
    'fo2': r'很(佛)(?=了|就)',
    'chong2': r'(重)(?=看的话)',
    'dang1': r'了(当)(?=然)',
    'fa5': r'头(发)(?=染|扎)',
    'jiang4': r'打麻(将)',
    'ren2': r'(任)(?=正非)',
    'de5': r'(?:安静|耐心|飞快|仔细|慢慢|匆忙|认真|轻轻|反复|一声不响|出乎意料|安安静静|长长|具体|不断|全面|合理|不停|完全|强行)(地)(?!区|带(?!上)|段|表|面|形|貌|质|理|域|球|下|上|方|图|位|点|震|毯|板|价|址|基)',
    'le5': r'(了)(?=然后|当然)',
    'zhe5': r'(?<=戴)(着)(?=眼镜)',
}
_EXTRA_READINGS = [
    ('dei3', r'^(得)(?=绕一下)'),
    ('dei3', r'我(得)(?=去系里)'),
    ('dei3', r'都(得)(?=学)'),
    ('dei3', r'那(得)(?=好几百)'),
    ('zhe5', r'(?<=玩)(着)(?=手机)'),
    ('chang2', r'(长)(?=曝光|时间)'),
    ('dou1', r'(?:在全国)(都)(?=这么)'),
    ('dou1', r'^(都)(?=会有更|会是那|会运用)'),  # Chinese run following English
    ('jiao1', r'普通话(教)(?=的)'),
    ('jiao1', r'^(教)(?=的就等于说)'),
    ('dai1', r'东部(待)(?=了)'),
    ('de5', r'(?:跑|笑|吹|说|擦|下|考|红|办|骑|做|急|玩|学|吃|搞|病|穿|安静|考虑|严重|变|恶化|觉不觉|不觉)(得)(?!到|分|奖|益|失|主|胜|法|手|力|意|罪|逞|救)'),
    ('de5', r'(?:项目|题目|超标)(的)(?=话|一些|$)'),
    ('de5', r'说打(的)(?=位置)'),
    ('fang5', r'(?:个|些|什么|的|某|多)地(方)(?!政府|财政|行政|自治|性法规)'),
    ('xi5', r'(?:个|些|种|买|的|什么|吃)东(西)(?!方|南北|部|两|海岸|方向)'),
]
_NEUTRAL_WORDS = {
    '衣服':'fu5', '朋友':'you5', '时候':'hou5', '清楚':'chu5', '舒服':'fu5',
    '喜欢':'huan5', '眼睛':'jing5', '商量':'liang5', '休息':'xi5', '行李':'li5',
    '消息':'xi5', '早上':'shang5', '明白':'bai5', '麻烦':'fan5',
}
_READING_RULES = [(re.compile(pattern), reading)
                  for reading, pattern in [*_CONTEXT_READINGS.items(), *_EXTRA_READINGS]]
_ORDINAL_ONE = re.compile(
    r'第(一)(?![一二三四五六七八九零])|[十百千万零](一)(?=日|楼|号|月|点[零一二三四五六七八九十]+分)|'
    r'(一)(?=月[零一二三四五六七八九十]+[日号])|月(一)(?=[日号])|'
    r'(一)(?=号房间)|住在(一)(?=楼)|(?:会议安排在|这趟列车)(一)(?=点[零一二三四五六七八九十]+分)'
)
_DIGIT_SEQUENCE = re.compile(r'[零一二三四五六七八九]{7,}')


def phrase_readings(phrase):
    """Lexical spellings shared by the acoustic tokens and the alignment transcript."""
    py = _pypinyin()
    readings = py.lazy_pinyin(phrase, style=py.Style.TONE3, neutral_tone_with_five=True, errors=list)
    for word, reading in _NEUTRAL_WORDS.items():
        for match in re.finditer(word, phrase):
            readings[match.end()-1] = reading
    for pattern, reading in _READING_RULES:
        for match in pattern.finditer(phrase):
            readings[match.start(1)] = reading
    # Use the inventory's nasal final for the syllabic nasal interjection.
    for index, char in enumerate(phrase):
        if char == '嗯' and readings[index][:-1] in ('n', 'ng'):
            readings[index] = 'en' + readings[index][-1]
    for index in fixed_one_positions(phrase):
        readings[index] = "yi1"
    return readings


def fixed_one_positions(phrase):
    positions = {match.start(match.lastindex) for match in _ORDINAL_ONE.finditer(phrase)}
    for match in _DIGIT_SEQUENCE.finditer(phrase):
        positions.update(i for i in range(*match.span()) if phrase[i] == '一')
    return positions


def apply_sandhi(syllables, fixed_ones=()):
    """Mandarin tone sandhi, applied left to right inside one phrase.

    * 不 (bu4) before a fourth tone -> second tone
    * 一 (yi1): before 4th -> 2nd; before 1st/2nd/3rd -> 4th; otherwise 1st
    * third tone + third tone -> second + third (iterative, so 3-3-3 -> 2-2-3)
    """
    result = list(syllables)
    count = len(result)
    for index, item in enumerate(result):
        if item is None:
            continue
        following = result[index + 1] if index + 1 < count else None
        if item.char == "不" and item.tone == 4 and following and following.tone == 4:
            result[index] = Syllable(item.initial, item.final, 2, item.char)
        elif item.char == "一" and item.tone == 1 and index not in fixed_ones:
            if following is None:
                continue
            if following.tone == 4:
                result[index] = Syllable(item.initial, item.final, 2, item.char)
            elif following.tone in (1, 2, 3):
                result[index] = Syllable(item.initial, item.final, 4, item.char)
    for index in range(count - 1):
        first, second = result[index], result[index + 1]
        if first and second and first.tone == 3 and second.tone == 3:
            result[index] = Syllable(first.initial, first.final, 2, first.char)
    return result


def phrase_syllables(phrase, readings=None):
    """Phonemize one run of text between punctuation marks."""
    if readings is None:
        readings = phrase_readings(phrase)
    syllables = []
    for index, value in enumerate(readings):
        char = phrase[index] if index < len(phrase) else "?"
        if not _CJK.match(char) or not value or not value[-1].isdigit():
            syllables.append(None)
            continue
        parts = split_pinyin(value)
        if parts is None:
            syllables.append(None)
            continue
        initial, final, tone = parts
        syllables.append(Syllable(initial, final, tone, char))
    return apply_sandhi(syllables, fixed_one_positions(phrase))


# --------------------------------------------------------------------------
# tokenisation
# --------------------------------------------------------------------------

def tokenize_with_owners(pieces):
    """Tokenise and say, for every token, which syllable it came from.

    ``owners[i]`` is the index of the syllable behind ``symbols[i]``, or ``-1``
    for punctuation and the boundary tokens. The aligner needs this: it learns
    where each character lies in the audio and must hand exactly those frames to
    that character's one or two tokens.
    """
    symbols, owners, unknown = [BOS], [-1], []
    syllable = -1
    for kind, value in pieces:
        if kind == "punct":
            if symbols[-1] != value:
                symbols.append(value)
                owners.append(-1)
            continue
        syllable += 1
        if value.initial:
            symbols.append(value.initial)
            owners.append(syllable)
        token = value.final + str(value.tone)
        if token in SYMBOL_TO_ID:
            symbols.append(token)
        else:
            unknown.append(token)
            symbols.append(UNK)
        owners.append(syllable)
    symbols.append(EOS)
    owners.append(-1)
    if not any(symbol in PHONE_SET or symbol == UNK for symbol in symbols):
        raise NothingToPronounce("the text has nothing to pronounce")
    return Phonemized(tuple(symbols), tuple(SYMBOL_TO_ID[s] for s in symbols),
                      tuple(0 for _ in symbols), tuple(unknown)), tuple(owners)


def tokenize(pieces):
    """Build the token sequence from ``(kind, value)`` pieces.

    ``kind`` is ``"punct"`` (a mark) or ``"syllable"`` (a ``Syllable``).
    Pure function: testable without audio and without pypinyin.
    """
    return tokenize_with_owners(pieces)[0]


def pieces(text):
    """Split normalized text into syllable and punctuation pieces."""
    output = []
    buffer = []

    def flush():
        if buffer:
            phrase = "".join(buffer)
            for syllable in phrase_syllables(phrase):
                output.append(("syllable", syllable) if syllable else ("punct", ""))
            buffer.clear()

    for char in text:
        if char in _PUNCTUATION_CHARS:
            flush()
            output.append(("punct", char))
        elif _CJK.match(char):
            buffer.append(char)
        elif char.isspace():
            flush()
        elif _LATIN_RUN.match(char):
            # Latin runs have no Mandarin reading here; they are reported, not guessed.
            flush()
            output.append(("punct", ""))
        else:
            continue
    flush()
    return [item for item in output if not (item[0] == "punct" and item[1] == "")]


def phonemize_with_owners(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must not be empty")
    normalized = normalize_text(text)
    if not normalized:
        raise NothingToPronounce("the text has nothing to pronounce")
    return tokenize_with_owners(pieces(normalized))


def phonemize(text):
    return phonemize_with_owners(text)[0]


def syllables_of(text):
    """The ``Syllable`` objects of ``text`` in order, matching token owners."""
    return [value for kind, value in pieces(normalize_text(text)) if kind == "syllable"]


def is_phone(token_ids):
    return [int(i) in PHONE_IDS for i in token_ids]
