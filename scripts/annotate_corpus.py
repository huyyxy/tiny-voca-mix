"""Write reusable text-only annotations using the same front end as inference."""
import argparse
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from tiny_voca.text import PHONE_IDS, SYMBOLS, frontend_fingerprint, phonemize


def annotate(corpus, output):
    fingerprint = frontend_fingerprint()
    output.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    failures = 0
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                            prefix=".annotations-", delete=False) as dest:
        temp = Path(dest.name)
        try:
            with corpus.open(encoding="utf-8") as source:
                for line in source:
                    row = json.loads(line)
                    uid = row["id"]
                    if uid in seen:
                        raise ValueError(f"Duplicate sample ID {uid}")
                    seen.add(uid)
                    try:
                        phones = phonemize(row["text"])
                        if (phones.unknown or SYMBOLS.index("<unk>") in phones.ids
                                or not PHONE_IDS.intersection(phones.ids)
                                or len(phones.stress) != len(phones.ids)
                                or tuple(SYMBOLS[i] for i in phones.ids) != phones.symbols):
                            raise ValueError("invalid or incomplete phonemizer output")
                    except ValueError as exc:
                        failures += 1
                        print(f"{uid}: {exc}", flush=True)
                        continue
                    record = {k: row[k] for k in ("id", "split", "language", "text_id")}
                    record.update(frontend=fingerprint, symbols=phones.symbols,
                                  tokens=phones.ids, stress=phones.stress)
                    dest.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            if failures:
                raise ValueError(f"Conversion failed for {failures} of {len(seen)} records")
            if not seen:
                raise ValueError("Empty input corpus")
            dest.flush()
            os.replace(temp, output)
        finally:
            temp.unlink(missing_ok=True)
    print(f"{len(seen)} entries written to {output} (frontend {fingerprint})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    annotate(args.corpus, args.output)
