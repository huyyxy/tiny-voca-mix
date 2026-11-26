# tiny-voca-mix

一个能在同一句话里切换普通话和英语的轻量 TTS 模型。输入「这个 weekend 我想去 hiking，你来吗？」，同一份权重会用 Vivian 的声音读完整句。模型从零训练了 **104,000 步**，包含 **4,575,499 个参数**，在 CPU 上输出 24 kHz 单声道语音。

[查看 Vivian 训练数据清单](dataset/vivian-bilingual/)（26,910 条样本，含训练、验证和测试划分）

## 浏览器合成

首次点击「合成」会将 Vivian ONNX 模型和中英文发音资源缓存到当前浏览器。看到「合成完成」后，可断网重新打开同一网址，输入新句子。清除网站数据后需重新下载。所有文本和生成的音频都留在设备上。[打开 Vivian](https://huyyxy.github.io/tiny-voca-mix/) · [下载 ONNX 权重](https://huyyxy.github.io/tiny-voca-mix/assets/vivian.onnx)

## 试听

### 中英混读

这个 weekend 我想去 hiking，你来吗？

https://github.com/user-attachments/assets/9a5d824d-5d93-4ed8-b660-29bc89a49af6

[下载原始 WAV](https://github.com/huyyxy/tiny-voca-mix/raw/refs/heads/main/docs/vivian-tts/assets/mixed.wav)

### 普通话

今天最低气温是负十度。

https://github.com/user-attachments/assets/5ff86c0f-1831-462d-ac07-738818ac5867

[下载原始 WAV](https://github.com/huyyxy/tiny-voca-mix/raw/refs/heads/main/docs/vivian-tts/assets/zh.wav)

### 英语

Could you open the window, please?

https://github.com/user-attachments/assets/5603f9b1-9277-4638-abfa-4e69068334b3

[下载原始 WAV](https://github.com/huyyxy/tiny-voca-mix/raw/refs/heads/main/docs/vivian-tts/assets/en.wav)

## 模型架构

中文声调和英文重音随音素进入同一个编码器。模型先预测每个音素占多少帧，再逐帧预测基频、清浊音和能量。谐波与噪声两条支路分别生成周期与非周期成分，相加得到语音波形。

![Vivian 模型架构：从双语音素、时长展开和韵律预测到谐波与噪声合成](docs/vivian-tts/assets/architecture.png)

## 在本地合成一句话

本地归档已将 Vivian 推理权重放在 `models/vivian-104000/inference.pt`。Git 默认忽略此文件。从源码克隆运行时，请把自己的兼容 Vivian 检查点放到该位置，或通过 `--checkpoint` 指定路径。只想试听时，可以直接使用上方播放器或下载原始 WAV。

以下命令在项目根目录执行。CPU 推理环境使用 Python 3.10，发音库由 `espeakng-loader` 提供。

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-local.txt
export PYTHONPATH="$PWD/src"

python -m tiny_voca.local_infer \
  --text '这个 weekend 我想去 hiking，你来吗？' \
  --output outputs/mixed.wav
```

需要交互试听时，在同一环境执行 `python web/server.py`，然后在浏览器中打开 `http://127.0.0.1:8766/`。模型运行在本机 Python 进程中。若端口已占用，可传入 `--port 8767`。

## 用 Qwen3-TTS 重新配音

在 Colab 打开[音色设计与批量合成笔记本](notebooks/Qwen3-TTS-VoiceDesign-Tiny-Voca-Mix.ipynb)，选择 GPU。输入是 `MyDrive/tiny-voca-mix-qwen3-tts/inputs/corpus.jsonl`，来自本地语料包中的 26,910 条中文、英文和混读文本。修改 `VOICE_DESCRIPTION` 可设计新音色，勾选 `PREVIEW_ONLY` 可先试听每类一句。`CONCURRENCY` 设置单 GPU 的批内并发数。参考音、模型和逐句 WAV 保存在同一 Drive 根目录，断线后用相同配置重新运行即可接续。

## 在 Colab 训练和续训

![Vivian 训练流程：将中文、英文和句内混读录音与文本对齐，提取特征并训练单音色模型](docs/vivian-tts/assets/training.png)

1. 把配对语料包放到 `MyDrive/tiny-voca-zh/downloads/vivian-bilingual.zip`。本地归档中的文件是 `data/vivian-bilingual.zip`。自备数据时按实验记录中的目录和字段组织，并沿用单音色配置。[数据格式与划分](docs/experiment.md) · [配置](config/prepare-config.json)
2. 在 Colab 上传训练笔记本，选择 GPU。首次运行可在首个代码单元设置 `SMOKE = True`，按顺序执行，分别从三类语料抽样，跑 80 步并试听。笔记本自带训练源码，会安装 Python 3.11、Torch/TorchAudio 2.8.0 和 eSpeak NG。[训练笔记本](notebooks/Vivian-Bilingual-Tiny-Voca.ipynb)
3. 将 `SMOKE` 改为 `False` 后重新按顺序执行，目标为 104,000 步。预处理每 128 条向 Drive 保存一个分块。训练每 500 步保存 `last.pt`，每 10,000 步额外保留快照。相同数据、前端和训练配置下，重新连接后按顺序执行即可恢复。末尾单元用 `inference.pt` 合成三种输入。

## 代码与实验记录

| 入口 | 内容 |
| --- | --- |
| [双语文本前端](src/tiny_voca/text.py) | 汉字转带调拼音，英文转音素并保留词重音，共用 277 个符号 |
| [特征提取与时长对齐](scripts/preprocess.py) | 用 MMS_FA 在同一条录音上定位中文音节和英文单词，生成每个音素的时长 |
| [模型](src/tiny_voca/model.py) · [训练入口](src/tiny_voca/train.py) | 从音素时长、韵律和声学特征生成波形，支持检查点恢复 |
| [实验记录](docs/experiment.md) | 语料来源、划分、训练配置、检查点位置及已知声调问题 |
| [训练图解](docs/vivian-tts/article.md) | 前端示例、模型架构图、训练流程和三段样音的频谱 |
| [来源及许可说明](NOTICE.md) | 上游代码、文本、音色与各自的来源 |

`data/` 和 `models/` 是本地归档目录。可以在项目根目录执行 `shasum -a 256 -c checksums.sha256` 核验本次实验的语料包和推理文件。

## 引用

### 上游项目

- Muhammed Nazeem 的 **tiny-voca** 提供了轻量语音合成模型和训练器。[项目仓库](https://github.com/n4ze3m/tiny-voca)
- xiaoliukuailiu 的 **tiny-voca-zh** 将模型适配到普通话。Vivian 的双语前端和训练笔记本以该项目的 `7ec7434` 版本为基础。[项目仓库](https://github.com/xiaoliukuailiu/tiny-voca-zh) · [实验使用的版本](https://github.com/xiaoliukuailiu/tiny-voca-zh/tree/7ec7434bb052fcd6da8066e77f7d0e160586e095)

```bibtex
@software{nazeem2026tinyvoca,
  author = {Nazeem, Muhammed},
  title  = {tiny-voca: a 4.5M-parameter two-voice English text-to-speech model},
  year   = {2026},
  url    = {https://huggingface.co/n4ze3m/tiny-voca}
}

@software{tiny-voca-zh,
  title  = {tiny-voca-zh: a 4.5M-parameter two-voice Mandarin text-to-speech model},
  year   = {2026},
  url    = {https://github.com/xiaoliukuailiu/tiny-voca-zh}
}
```

### 相关论文

- Holy Lovenia 等，LREC 2022。实验选取 ASCEND 的中英混读对话转写，由 Vivian 逐句朗读，构成句内语言切换的训练样本。[ASCEND: A Spontaneous Chinese-English Dataset for Code-switching in Multi-turn Conversation](https://aclanthology.org/2022.lrec-1.788/)
- Vineel Pratap 等，JMLR 2024。预处理使用 MMS 项目的多语言强制对齐模型，通过 TorchAudio 的 `MMS_FA` 定位录音里的中文音节和英文单词。[Scaling Speech Technology to 1,000+ Languages](https://jmlr.org/papers/v25/23-1318.html)
