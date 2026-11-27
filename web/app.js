const el = id => document.getElementById(id);
fetch('/voices').then(r => r.json()).then(voices => {
  const labels = {male:'男播音员', female:'女播音员'};
  for (const voice of voices) el('voice').add(new Option(labels[voice] || voice, voice));
  el('speak').disabled = !voices.length;
}).catch(error => { el('status').textContent = error.message; });
el('speed').oninput = () => el('rate').value = Number(el('speed').value).toFixed(2);
el('speak').onclick = async () => {
  el('speak').disabled = true;
  el('status').textContent = '正在合成…';
  try {
    const response = await fetch('/synthesize', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:el('text').value,speed:el('speed').value,voice:el('voice').value})});
    if (!response.ok) throw Error(await response.text());
    const audio = el('audio');
    if (audio.src) URL.revokeObjectURL(audio.src);
    audio.src = URL.createObjectURL(await response.blob());
    audio.hidden = false;
    el('status').textContent = '合成完成。';
    await audio.play().catch(() => {});
  } catch (error) { el('status').textContent = error.message; }
  finally { el('speak').disabled = false; }
};
