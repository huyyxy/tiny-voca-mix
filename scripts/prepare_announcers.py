"""Join the two full Qwen runs with the frozen Misaki inputs for Colab training."""
import hashlib
import json
from collections import Counter
from pathlib import Path

SPEAKERS = ('male', 'female')
SPLITS = ('train', 'validation', 'test')
CORPUS_SHA256 = '582ad8a8b4a395bc63e4ad3714ef278ab760e1a126e290478f317cc2a1b5961a'


def load_by_id(path):
    records = {}
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            if row['id'] in records:
                raise ValueError(f"Duplicate ID {row['id']} in {path}")
            records[row['id']] = row
    return records


def prepare(root, data, frontend):
    corpus_file = root / 'inputs/corpus.jsonl'
    if hashlib.sha256(corpus_file.read_bytes()).hexdigest() != CORPUS_SHA256:
        raise ValueError('Expected the 31,799-sentence corpus supplied with the notebooks')
    corpus = load_by_id(corpus_file)
    labels = load_by_id(root / 'inputs/misaki.jsonl')
    if labels.keys() != corpus.keys():
        raise ValueError('Misaki annotation IDs differ from the corpus')
    for uid, row in corpus.items():
        label = labels[uid]
        if (any(label[k] != row[k] for k in ('language', 'split', 'text_id'))
                or label['frontend'] != frontend):
            raise ValueError(f'Annotation metadata or frontend differs for {uid}')

    runs = json.loads((root / 'announcers.json').read_text())
    if set(runs) != set(SPEAKERS) or len(set(runs.values())) != len(SPEAKERS):
        raise ValueError('Expected two distinct completed Qwen runs')
    rows = {split: [] for split in SPLITS}
    voices = set()
    references = set()
    for speaker in SPEAKERS:
        run_id = runs[speaker]
        if len(run_id) != 16 or any(c not in '0123456789abcdef' for c in run_id):
            raise ValueError(f'Invalid run ID for {speaker}')
        folder = root / 'runs' / run_id
        recipe_bytes = (folder / 'recipe.json').read_bytes()
        recipe = json.loads(recipe_bytes)
        if (hashlib.sha256(recipe_bytes).hexdigest()[:16] != run_id
                or recipe['corpus_sha256'] != CORPUS_SHA256 or recipe['voice'] in voices
                or recipe['reference_sha256'] in references):
            raise ValueError(f'Incorrect corpus, run or duplicate reference voice for {speaker}')
        voices.add(recipe['voice'])
        references.add(recipe['reference_sha256'])
        recordings = load_by_id(folder / 'corpus.jsonl')
        if recordings.keys() != corpus.keys():
            raise ValueError(f'{speaker} requires one recording of every sentence')
        for uid, sentence in corpus.items():
            record = recordings[uid]
            bucket = hashlib.sha256(uid.encode()).hexdigest()[:2]
            relative = Path('audio', sentence['language'], bucket, uid + '.wav')
            path = folder / relative
            if (any(record[k] != sentence[k] for k in ('text', 'text_id', 'language', 'split'))
                    or record['audio'] != relative.as_posix() or record['voice_id'] != recipe['voice']
                    or record['sample_rate'] != 24000 or record['seconds'] <= 0):
                raise ValueError(f'Recording metadata differs for {speaker}/{uid}')
            if not path.is_file():
                raise FileNotFoundError(path)
            label = labels[uid]
            rows[sentence['split']].append({
                **record, 'id': f'{speaker}-{uid}', 'sentence_id': uid, 'voice_id': speaker,
                'source_id': run_id, 'audio': str(path.resolve()), 'origin': 'qwen3-tts',
                'tokens': label['tokens'], 'stress': label['stress'], 'frontend': frontend,
            })
    data.mkdir(parents=True, exist_ok=True)
    for split, items in rows.items():
        with (data / f'{split}.jsonl').open('w', encoding='utf-8') as stream:
            for row in items:
                print(json.dumps(row, ensure_ascii=False), file=stream)
        print(split, dict(Counter(r['voice_id'] for r in items)), flush=True)
    (data / 'prepare-config.json').write_text(json.dumps({'speakers': SPEAKERS}))
