"""Score frozen word/character readings on full-sentence frontend output."""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

from tiny_voca.text import VOWELS, units
from tiny_voca.zh_text import split_pinyin

ROOT = Path(__file__).resolve().parents[1]
WORDS = re.compile(r"[A-Za-z]+|[一-鿿]")


def english_key(pronunciation):
    # US broad phonemic transcription: abstract away vowel length, flapping,
    # and alternate notation for rhotic, reduced and syllabic vowels.
    return (pronunciation.replace("ː", "").replace("ɾ", "t")
            .replace("ɜɹ", "ɚ").replace("əɹ", "ɚ").replace("ᵻ", "ɪ")
            .replace("ɐ", "ə").replace("n̩", "ən"))


def score(reference, sentence):
    if "unit" not in reference:
        targets = [phones for word, phones in units(sentence) if word == reference["target"]]
        if len(targets) != 1:
            return False, "word missing or not unique"
        if "primary_vowel" in reference:
            stresses = [stress for symbol, stress in targets[0] if symbol in VOWELS]
            primary = [i for i, stress in enumerate(stresses) if stress == 1]
            return primary == [reference["primary_vowel"]], primary
        actual = "".join(symbol.removeprefix("en/") for symbol, _ in targets[0])
        return english_key(actual) in [english_key(r) for r in reference["expected"]], actual
    tokens = WORDS.findall(sentence)
    index = reference["unit"]
    assert tokens[index] == reference["target"]
    pronounced = [(word, phones) for word, phones in units(sentence) if word]
    if len(tokens) != len(pronounced):
        return False, "unit-count mismatch"
    word, phones = pronounced[index]
    marks = [sym.split("/", 1)[-1] for sym, _ in phones]
    if reference["target"].isascii():
        if word != tokens[index].lower():
            return False, "word mismatch"
        actual = "".join(marks)
        return any(english_key(actual) == english_key(r) for r in reference["expected"]), actual
    for candidate in reference["expected"]:
        parts = split_pinyin(candidate)
        if parts:
            initial, final, tone = parts
            if marks == ([initial] if initial else []) + [final + str(tone)]:
                return True, candidate
    return False, " ".join(marks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--annotations", type=Path,
                        help="Check saved symbols and stress against the same sentences during scoring")
    args = parser.parse_args()
    saved = {}
    if args.annotations:
        ids = {r["id"] for path in (ROOT / "tests" / "fixtures").glob("misaki-*-references.jsonl")
               for r in map(json.loads, path.open())}
        with args.annotations.open() as annotation_file:
            saved = {r["id"]: r for r in map(json.loads, annotation_file) if r["id"] in ids}
        if set(saved) != ids:
            raise ValueError("Missing evaluation sentences from annotations")
    corpus = {r["id"]: r["text"] for r in map(json.loads, args.corpus.open())}
    scores = Counter()
    with args.output.open("w") as out:
        for suite in ("reading", "polyphone", "heteronym", "stress"):
            path = ROOT / "tests" / "fixtures" / f"misaki-{suite}-references.jsonl"
            for ref in map(json.loads, path.open()):
                try:
                    sentence = corpus[ref["id"]]
                    if args.annotations:
                        row = saved[ref["id"]]
                        pairs = [pair for _, phones in units(sentence) for pair in phones]
                        if [symbol for symbol, _ in pairs] != row["symbols"]:
                            raise RuntimeError(f"Saved symbols differ for {ref['id']}")
                        if [stress for _, stress in pairs] != row["stress"]:
                            raise RuntimeError(f"Saved stress differs for {ref['id']}")
                    passed, actual = score(ref, sentence)
                except ValueError as err:
                    passed, actual = False, str(err)
                scores[suite, ref["language"], passed] += 1
                print(json.dumps(dict(**ref, suite=suite, passed=passed, actual=actual),
                                 ensure_ascii=False), file=out)
    print(sorted(scores.items()))


if __name__ == "__main__":
    main()
