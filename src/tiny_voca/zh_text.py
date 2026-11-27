"""Mandarin phone inventory, text normalization and context readings for Misaki."""
from dataclasses import dataclass
import re
import unicodedata

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
VOWELS = FINAL_TOKENS

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


def fixed_one_positions(phrase):
    positions = {match.start(match.lastindex) for match in _ORDINAL_ONE.finditer(phrase)}
    for match in _DIGIT_SEQUENCE.finditer(phrase):
        positions.update(i for i in range(*match.span()) if phrase[i] == '一')
    return positions
