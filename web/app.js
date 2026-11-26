const el = id => document.getElementById(id);
const status = el('status');
const button = el('speak');
const audio = el('audio');
let worker;

el('speed').oninput = () => el('rate').value = Number(el('speed').value).toFixed(2);

async function prepareOffline() {
  if (!('serviceWorker' in navigator)) throw Error('请使用支持离线存储的浏览器，通过 HTTPS 打开此页面。');
  const sw = navigator.serviceWorker;
  if (sw.controller) return;
  status.textContent = '正在下载并保存离线资源，首次使用可能需要一点时间…';
  const registration = await sw.register('./sw.js');
  if (sw.controller) return;
  const installing = registration.installing || registration.waiting || registration.active;
  if (!installing) throw Error('离线资源未安装，请联网后重试。');
  await new Promise((resolve, reject) => {
    function check() {
      if (!sw.controller && installing.state !== 'redundant') return;
      sw.removeEventListener('controllerchange', check);
      installing.removeEventListener('statechange', check);
      if (sw.controller) resolve();
      else reject(Error('离线资源下载未完成，请检查网络和浏览器存储空间后重试。'));
    }
    sw.addEventListener('controllerchange', check);
    installing.addEventListener('statechange', check);
    check();
  });
}

function showError(message) {
  status.textContent = message;
  button.disabled = false;
}

button.onclick = async () => {
  const text = el('text').value.trim();
  if (!text) return showError('请输入要合成的中文或英文。');
  button.disabled = true;
  try {
    await prepareOffline();
    if (!worker) {
      worker = new Worker('./worker.js');
      worker.onerror = event => {
        worker.terminate();
        worker = undefined;
        showError('浏览器推理启动失败。' + (event.message || '请刷新后重试。'));
      };
      worker.onmessage = ({data}) => {
        if (data.status) {
          status.textContent = data.status;
        } else if (data.error) {
          showError(data.error);
        } else {
          if (audio.src) URL.revokeObjectURL(audio.src);
          audio.src = URL.createObjectURL(new Blob([data.wav], {type: 'audio/wav'}));
          audio.hidden = false;
          status.textContent = '合成完成。此浏览器已可离线使用。';
          button.disabled = false;
          audio.play().catch(() => {});
        }
      };
    }
    worker.postMessage({text, speed: Number(el('speed').value)});
  } catch (error) {
    showError(error.message);
  }
};
