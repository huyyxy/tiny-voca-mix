"""Align each recording using MMS words/syllables and cache small chunks on Drive."""
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from contextlib import nullcontext
from itertools import islice
import hashlib, json, os, shutil, sys, tarfile, tempfile, time
from pathlib import Path
import torch, torchaudio
from torchaudio.pipelines import MMS_FA
from tiny_voca.config import Config
from tiny_voca.prepare import _prepare_row
from tiny_voca.text import units, frontend_fingerprint

model=None
tokenizer = MMS_FA.get_tokenizer()
aligner = MMS_FA.get_aligner()

def prepare_cpu(task):
    source, index, row, config, split, folder = task
    try:
        if len(row["tokens"]) > config.max_tokens:
            raise ValueError("Too many tokens")
        record, wave = _prepare_row(source, 0, index, row, config, "text", "voice_id", split,
                                    folder, return_wave=True)
        return record, wave.numpy(), None
    except ValueError as exc:
        return None, None, str(exc)


@torch.inference_mode()
def emissions(waves):
    global model
    if model is None:
        model = MMS_FA.get_model().eval().cuda()
    signals = [torchaudio.functional.resample(torch.from_numpy(w), 24000, 16000).cuda()
               for w in waves]
    # TorchAudio 2.8 normalizes the whole input tensor and appends a single-item
    # star channel. Apply its wrapper operations per utterance around one batched encoder.
    if model.normalize_waveform:
        signals = [torch.nn.functional.layer_norm(x, x.shape) for x in signals]
    lengths = torch.tensor([x.numel() for x in signals], device="cuda")
    padded = torch.nn.utils.rnn.pad_sequence(signals, batch_first=True)
    logits, valid = model.model(padded, lengths)
    if model.apply_log_softmax:
        logits = logits.log_softmax(dim=-1)
    if model.append_star:
        logits = torch.cat((logits, torch.zeros_like(logits[:, :, :1])), dim=-1)
    return [item[:length] for item, length in zip(logits, valid.tolist())]


@torch.inference_mode()
def durations(text, emission, frames):
    groups=units(text)
    words=[w for w,_ in groups if w]
    labels=tokenizer(words)
    flat=[v for group in labels for v in group]
    if not all(labels) or len(flat)+sum(a==b for a,b in zip(flat,flat[1:]))>emission.size(0):
        raise ValueError("CTC target exceeds emission length")
    spans=iter(aligner(emission,labels))
    scale=frames/emission.size(0)
    centers=[]
    voiced=[]
    for word,phones in groups:
        if word:
            span=next(spans)
            lo,hi=span[0].start*scale,span[-1].end*scale
            for j,(symbol,_) in enumerate(phones):
                centers.append(lo+(j+.5)*(hi-lo)/len(phones))
                voiced.append("/" in symbol)
        else:
            centers.append(None)
            voiced.append(False)
    # Anchor punctuation/boundaries in available gaps. Each pronounced phone gets >= 1 frame.
    if sum(voiced)>frames: raise ValueError("Too many phones")
    centers[0],centers[-1]=0.,float(frames)
    import numpy as np
    indices=[i for i,v in enumerate(centers) if v is not None]
    curve=np.interp(np.arange(len(centers)),indices,[centers[i] for i in indices])
    cuts=np.rint((curve[:-1]+curve[1:])/2).astype(int)
    result=[]
    pos=0
    remaining=sum(voiced)
    for i,cut in enumerate([*cuts,frames]):
        remaining-=voiced[i]
        end=min(frames-remaining,max(pos+int(voiced[i]),int(cut)))
        result.append(end-pos)
        pos=end
    return result

def dump(file,rows):
    file.write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in rows))

def main():
    data, local, drive = map(Path,sys.argv[1:4])
    c=Config.from_dict(json.loads((data/"prepare-config.json").read_text()))
    local.mkdir(parents=True,exist_ok=True)
    key=hashlib.sha256()
    for name in ("train","validation","test"):
        key.update((data/(name+".jsonl")).read_bytes())
    key.update((frontend_fingerprint()+c.fingerprint).encode())
    # Bump when feature extraction or alignment semantics change.
    key.update(b"announcers-features-v1")
    tag=key.hexdigest()
    cache=drive/"preparation"/tag
    cache.mkdir(parents=True,exist_ok=True)
    workers = int(sys.argv[4]) if len(sys.argv)>4 else 1
    gpu_batch = int(sys.argv[5]) if len(sys.argv)>5 else 1
    if min(workers, gpu_batch) < 1:
        raise ValueError("预处理并发数和 GPU 批大小必须为正整数")
    for setting in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS", "NUMBA_NUM_THREADS"):
        os.environ[setting] = "1"
    torch.set_num_threads(1)
    print(f"预处理 CPU 进程 {workers}，GPU 对齐批大小 {gpu_batch}", flush=True)
    total = sum(len((data/(split+".jsonl")).read_bytes().splitlines()) for split in ("train","validation","test"))
    processed = computed = 0
    compute_seconds = 0.0
    executor = (ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context("spawn"))
                if workers > 1 else nullcontext(None))
    with executor as pool:
        for split in ("train","validation","test"):
            source=data/(split+".jsonl")
            rows=list(map(json.loads,source.read_text().splitlines()))
            (local/split).mkdir(exist_ok=True)
            accepted=[]; rejected=[]
            for offset in range(0,len(rows),128):
                label=f"{split}-{offset:05d}"
                archive=cache/(label+".tar")
                good=local/(label+".jsonl"); bad=local/(label+".rejected.jsonl")
                started = time.monotonic()
                marker = local/(label+".ready")
                if marker.exists() and marker.read_text() == tag and good.is_file() and bad.is_file() and all(
                    (local/json.loads(line)["path"]).is_file() for line in good.read_text().splitlines()
                ):
                    action = "local"
                elif archive.exists():
                    action = "restore"
                    marker.unlink(missing_ok=True)
                    with tempfile.TemporaryDirectory(dir=local) as scratch:
                        packed = Path(scratch)/archive.name
                        shutil.copyfile(archive, packed)
                        with tarfile.open(packed) as t:
                            t.extractall(local, filter="data")
                else:
                    action = "compute"
                    marker.unlink(missing_ok=True)
                    batch=[]; failures=[]
                    chunk = rows[offset:offset+128]
                    tasks = ((source, offset+i, row, c, split, local/split) for i, row in enumerate(chunk))
                    results = pool.map(prepare_cpu, tasks) if pool else map(prepare_cpu, tasks)
                    paired = zip(chunk, results)
                    while group := list(islice(paired, gpu_batch)):
                        ready = []
                        for row, (record, wave, error) in group:
                            if error is None:
                                ready.append((row, record, wave))
                            else:
                                failures.append(dict(id=row["id"], language=row["language"], reason=error))
                        if not ready:
                            continue
                        scores = emissions([wave for _, _, wave in ready])
                        for (row, record, _), emission in zip(ready, scores):
                            try:
                                d = durations(row["text"], emission, record["frames"])
                                assert len(d)==len(row["tokens"]) and sum(d)==record["frames"]
                                record.update(tokens=row["tokens"], stress=row["stress"], durations=d,
                                              language=row["language"], frontend=row["frontend"], annotation=tag)
                                batch.append(record)
                            except ValueError as exc:
                                failures.append(dict(id=row["id"], language=row["language"], reason=str(exc)))
                    count = len(chunk)
                    dump(good,batch); dump(bad,failures)
                    with tempfile.TemporaryDirectory(dir=local) as scratch:
                        packed = Path(scratch)/archive.name
                        with tarfile.open(packed,"w") as t:
                            for path in [good,bad,*[local/r["path"] for r in batch]]:
                                t.add(path,arcname=path.relative_to(local))
                        with tempfile.NamedTemporaryFile(dir=cache, suffix=".partial", delete=False) as upload:
                            tmp = Path(upload.name)
                        try:
                            shutil.copyfile(packed, tmp)
                            os.replace(tmp, archive)
                        finally:
                            tmp.unlink(missing_ok=True)
                if action != "local":
                    marker.write_text(tag)
                print(f"{label} {action} {time.monotonic()-started:.2f}s",flush=True)
                processed += min(128, len(rows)-offset)
                if action == "compute":
                    computed += count
                    compute_seconds += time.monotonic() - started
                    rate = 60 * computed / compute_seconds
                    print(f"预处理 {rate:.1f} 段/分钟，按剩余全需计算估计 {(total-processed)/rate:.1f} 分钟", flush=True)
                accepted.extend(map(json.loads,good.read_text().splitlines()))
                rejected.extend(map(json.loads,bad.read_text().splitlines()))
                print(split,offset+min(128,len(rows)-offset),"/",len(rows),"accepted",len(accepted),flush=True)
            dump(local/(split+".jsonl"),accepted)
            dump(cache/(split+".rejected.jsonl"),rejected)
            for lang in ("zh","en","mixed"):
                n=sum(r["language"]==lang for r in rows)
                used=sum(r["language"]==lang for r in accepted)
                print(split,lang,used,"/",n)
                if not n or used<.8*n: raise ValueError("Inspect rejection log before training")
        (local/"annotations.json").write_text(json.dumps(dict(complete=True,fingerprint=tag,acoustic_root=str(local))))


if __name__ == "__main__":
    main()
