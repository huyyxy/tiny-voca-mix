"""Vivian Mandarin/English frontend shared by annotation and synthesis."""
import hashlib
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
import pypinyin
from . import zh_text as zh, en_text as en

LANGUAGE = "mixed"
DEFAULT_SPEAKERS = ("Vivian",)
FRONTENDS = ("vivian-mixed",)
FRONTEND_VARIABLE = "VIVIAN_FRONTEND"
NothingToPronounce = zh.NothingToPronounce
SYMBOLS = zh.SPECIALS + zh.PUNCTUATION + tuple("zh/"+p for p in zh.PHONES) + tuple("en/"+p for p in en.PHONES)
SYMBOL_TO_ID = {p:i for i,p in enumerate(SYMBOLS)}
PHONE_IDS = {i for i,p in enumerate(SYMBOLS) if "/" in p}
VOWELS = tuple("zh/"+p for p in zh.VOWELS) + tuple("en/"+p for p in en.VOWELS)
def set_frontend(name):
    if name not in FRONTENDS:
        raise ValueError(name)
def frontend_identity():
    return dict(phonemizer=FRONTENDS[0], symbols=list(SYMBOLS))
@lru_cache()
def frontend_fingerprint():
    h = hashlib.sha256()
    for module in (__file__, zh.__file__, en.__file__):
        h.update(Path(module).read_bytes())
    h.update((pypinyin.__version__ + en.espeak_version()).encode())
    return h.hexdigest()

@lru_cache(maxsize=16000)
def english(word):
    phones = en.phonemize(word)
    if phones.unknown:
        raise ValueError(f"Unmapped English phoneme in {word}")
    return [(("en/"+p if p in en.PHONE_SET else p), s) for p,s in zip(phones.symbols[1:-1],phones.stress[1:-1])]

def units(text):
    from num2words import num2words
    text = unicodedata.normalize("NFKC", text).replace("’","'")
    han = r"[\u3400-\u9fff]"
    if re.search(han,text):
        text = zh.normalize_text(re.sub(r"[-−](?=\d)", "负", text))
    else:
        text = re.sub(r"-?\d+(?:\.\d+)?",lambda m:num2words(m.group()),text)
    tokens = re.findall(han+r"+|[A-Za-z]+(?:'[A-Za-z]+)*|[^\s]",text)
    out = [("",[(zh.BOS,0)])]
    for part in tokens:
        if re.fullmatch(han+"+",part):
            syllables = zh.phrase_syllables(part)
            roman = pypinyin.lazy_pinyin(part,style=pypinyin.Style.NORMAL)
            if len(roman)!=len(syllables) or None in syllables:
                raise ValueError(f"Unmapped Mandarin syllable in {part}")
            for spelling,sy in zip(roman,syllables):
                phones = ([sy.initial] if sy.initial else []) + [sy.final+str(sy.tone)]
                out.append((spelling.replace("ü","u").replace("v","u"),[("zh/"+p,0) for p in phones]))
        elif re.match("[A-Za-z]",part):
            if out[-1][0]:
                out.append(("",[(zh.SP,0)]))
            out.append((part.lower().replace("'",""), english(part)))
        elif part in zh.PUNCTUATION:
            out.append(("",[(part,0)]))
    if not any(word for word,_ in out):
        raise NothingToPronounce(text)
    return out+[("",[(zh.EOS,0)])]

def phonemize(text):
    pairs=[pair for _,phones in units(text) for pair in phones]
    symbols,stress=zip(*pairs)
    return zh.Phonemized(symbols,tuple(SYMBOL_TO_ID[s] for s in symbols),stress,())
