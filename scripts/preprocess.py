"""Align each recording using MMS words/syllables and cache small chunks on Drive."""
import collections, hashlib, json, os, shutil, sys, tarfile
from pathlib import Path
import torch, torchaudio
from torchaudio.pipelines import MMS_FA
from tiny_voca.config import Config
from tiny_voca.prepare import _prepare_row
from tiny_voca.text import units, phonemize, frontend_fingerprint

data, local, drive = map(Path,sys.argv[1:4])
c=Config(speakers=("Vivian",))
local.mkdir(parents=True,exist_ok=True)
key=hashlib.sha256()
for name in ("train","validation","test"):
    key.update((data/(name+".jsonl")).read_bytes())
key.update((frontend_fingerprint()+c.fingerprint).encode())
key.update(Path(__file__).read_bytes())
tag=key.hexdigest()
cache=drive/"preparation"/tag
cache.mkdir(parents=True,exist_ok=True)
model=None

@torch.inference_mode()
def durations(text,wave,frames):
    global model
    if model is None:
        model=MMS_FA.get_model().eval().cuda()
    groups=units(text)
    words=[w for w,_ in groups if w]
    x=torchaudio.functional.resample(wave,24000,16000).unsqueeze(0).cuda()
    emission,_=model(x)
    labels=MMS_FA.get_tokenizer()(words)
    flat=[v for group in labels for v in group]
    if not all(labels) or len(flat)+sum(a==b for a,b in zip(flat,flat[1:]))>emission.size(1):
        raise ValueError("CTC target exceeds emission length")
    spans=iter(MMS_FA.get_aligner()(emission[0],labels))
    scale=frames/emission.size(1)
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

torch.set_num_threads(1)
for split in ("train","validation","test"):
    source=data/(split+".jsonl")
    rows=list(map(json.loads,source.read_text().splitlines()))
    (local/split).mkdir(exist_ok=True)
    accepted=[]; rejected=[]
    for offset in range(0,len(rows),128):
        label=f"{split}-{offset:05d}"
        archive=cache/(label+".tar")
        good=local/(label+".jsonl"); bad=local/(label+".rejected.jsonl")
        if archive.exists():
            with tarfile.open(archive) as t: t.extractall(local,filter="data")
        else:
            batch=[]; failures=[]
            for i,row in enumerate(rows[offset:offset+128],offset):
                try:
                    ph=phonemize(row["text"])
                    if len(ph)>c.max_tokens: raise ValueError("Too many tokens")
                    record=_prepare_row(source,0,i,row,c,"text","voice_id",split,local/split)
                    wave=torch.load(local/record["path"],weights_only=True)["wave"]
                    d=durations(row["text"],wave,record["frames"])
                    assert len(d)==len(ph) and sum(d)==record["frames"]
                    record.update(tokens=ph.ids,stress=ph.stress,durations=d,language=row["language"],
                                  frontend=frontend_fingerprint(),annotation=tag)
                    batch.append(record)
                except ValueError as exc:
                    failures.append(dict(id=row["id"],language=row["language"],reason=str(exc)))
            dump(good,batch); dump(bad,failures)
            tmp=archive.with_suffix(".partial")
            with tarfile.open(tmp,"w") as t:
                for path in [good,bad,*[local/r["path"] for r in batch]]:
                    t.add(path,arcname=path.relative_to(local))
            os.replace(tmp,archive)
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
