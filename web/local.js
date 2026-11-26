const el = id => document.getElementById(id);
el('mode').textContent = '本机 Python 语音合成';
el('status').textContent = '';
el('speed').oninput = () => el('rate').value = Number(el('speed').value).toFixed(2);
el('speak').onclick = async () => {
  el('speak').disabled = true;
  el('status').textContent = '正在合成…';
  try {
    const response = await fetch('/synthesize', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:el('text').value,speed:el('speed').value})});
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
