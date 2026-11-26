const asset = path => new URL('assets/' + path, self.location.href).href;
importScripts(asset('pyodide/pyodide.js'), asset('ort/dist/ort.wasm.min.js'));

let session, config, phonemize;

async function initialize() {
  const {createEspeak} = await import(asset('espeak/dist/browser.js'));
  const [py, espeak, archive, metadata] = await Promise.all([
    loadPyodide({indexURL: asset('pyodide/')}),
    createEspeak({dataUrl: asset('espeak/espeak-ng-data/')}),
    fetch(asset('frontend.zip')).then(response => response.arrayBuffer()),
    fetch(asset('vivian.json')).then(response => response.json()),
  ]);
  config = metadata;
  espeak.setVoice('en-us');
  py.registerJsModule('browser_speech', {
    english_ipa: word => espeak.phonemes(word, {separator: '_'}),
  });
  py.unpackArchive(archive, 'zip', {extractDir: '/vivian'});
  py.runPython(`
import sys, json
sys.path.insert(0, '/vivian')
from browser_speech import english_ipa
from tiny_voca import text, en_text
en_text.espeak_words = lambda word: en_text.parse_espeak(english_ipa(word))

def phonemize_json(phrase):
    try:
        result = text.phonemize(phrase)
    except text.NothingToPronounce:
        return 'null'
    return json.dumps([result.ids, result.stress])
`);
  phonemize = py.globals.get('phonemize_json');
  ort.env.wasm.numThreads = 1;
  ort.env.wasm.wasmPaths = asset('ort/dist/');
  session = await ort.InferenceSession.create(asset('vivian.onnx'), {executionProviders: ['wasm']});
}

// Bound the frame-level attention matrix on phones and low-memory devices.
function* utterances(phrase) {
  const phones = JSON.parse(phonemize(phrase));
  if (!phones) return;
  if (phones[0].length <= Math.min(90, config.max_tokens)) {
    yield phones;
    return;
  }
  const middle = Math.floor(phrase.length / 2);
  const breaks = [...phrase.matchAll(/[，,；;：:、\s]|[\u3400-\u9fff]/gu)]
    .map(match => match.index + 1).filter(i => i < phrase.length);
  const cut = breaks.length ? breaks.reduce((a, b) =>
    Math.abs(a - middle) <= Math.abs(b - middle) ? a : b) : middle;
  if (!cut) throw Error('单个词超过模型支持的长度。');
  yield* utterances(phrase.slice(0, cut));
  yield* utterances(phrase.slice(cut));
}

function ints(values, dims) {
  return new ort.Tensor('int64', BigInt64Array.from(values, BigInt), dims);
}
function scalar(value) {
  return new ort.Tensor('float32', Float32Array.of(value), [1]);
}

async function speak(text, speed) {
  if (!/[.!?…,;:。！？；：、]$/u.test(text)) text += '。';
  const pieces = text.split(/(?<=[。！？!?…])|(?<=\.)\s+/u).filter(piece => piece.trim());
  const clips = [];
  for (const piece of pieces) {
    for (const [ids, stress] of utterances(piece)) {
      const result = await session.run({
        tokens: ints(ids, [1, ids.length]), stress: ints(stress, [1, ids.length]),
        voice: ints([0], [1]), speed: scalar(speed), pitch_shift: scalar(0), pitch_range: scalar(1),
      });
      clips.push(result.audio.data);
    }
  }
  if (!clips.length) throw Error('请输入可朗读的中文、英文或数字。');
  const samples = clips.reduce((n, clip) => n + clip.length, 0);
  const wav = new ArrayBuffer(44 + samples * 2);
  const view = new DataView(wav);
  function tag(at, value) {
    for (let i = 0; i < value.length; i++) view.setUint8(at + i, value.charCodeAt(i));
  }
  tag(0, 'RIFF');
  view.setUint32(4, 36 + samples * 2, true);
  tag(8, 'WAVE'); tag(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, config.sample_rate, true);
  view.setUint32(28, config.sample_rate * 2, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  tag(36, 'data'); view.setUint32(40, samples * 2, true);
  let peak = 0;
  for (const clip of clips) for (const sample of clip) peak = Math.max(peak, Math.abs(sample));
  if (!Number.isFinite(peak) || !peak) throw Error('模型未生成有效音频。');
  const scale = 32767 * Math.min(1, 0.99 / peak);
  let offset = 44;
  for (const clip of clips) {
    for (const sample of clip) {
      view.setInt16(offset, Math.round(sample * scale), true);
      offset += 2;
    }
  }
  return wav;
}

self.onmessage = async ({data}) => {
  try {
    if (!session) {
      postMessage({status: '正在启动本机模型…'});
      await initialize();
    }
    postMessage({status: '正在浏览器中合成…'});
    const wav = await speak(data.text, data.speed);
    postMessage({wav}, [wav]);
  } catch (error) {
    postMessage({error: error.message || String(error)});
  }
};
