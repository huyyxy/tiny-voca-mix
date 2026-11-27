# tiny-voca-mix

一个能在同一句话里切换普通话和英语的轻量 TTS 模型。输入「这个 weekend 我想去 hiking，你来吗？」，同一份权重会用 Vivian 的声音读完整句。模型从零训练了 **104,000 步**，包含 **4,575,499 个参数**，在 CPU 上输出 24 kHz 单声道语音。

[查看双语文本清单](dataset/)（31,799 条，含全部 8,750 句英文，按句子划分训练、验证和测试集）。

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

下面使用新版 Misaki 前端训练导出的双播音员检查点。将命令中的路径换成实际的 `inference.pt`。本地命令和浏览器界面共用同一个 Python 推理入口。

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-local.txt
export PYTHONPATH="$PWD/src"

python -m tiny_voca.local_infer --checkpoint /path/to/inference.pt \
  --voice female --text '这个 weekend 我想去 hiking，你来吗？' --output outputs/mixed.wav
python web/server.py --checkpoint /path/to/inference.pt
```

本地界面默认地址为 `http://127.0.0.1:8766/`。

## 用 Qwen3-TTS 重新配音

将仓库中的 [Colab 输入包](data/tiny-voca-mix-colab-31799.zip) 上传到 MyDrive 根目录，然后在 Colab 运行[男女播音员生成笔记本](notebooks/Qwen3-TTS-VoiceDesign-Tiny-Voca-Mix.ipynb)。笔记本从包内提取 31,799 条原文与 Misaki 标注，为男、女播音员各生成一段参考音，再依次合成全部原句。勾选 `PREVIEW_ONLY` 可先听两种音色的三类示例，保持音色配置可断线续跑。两份全量清单均完成后才更新 `MyDrive/tiny-voca-mix-qwen3-tts/announcers.json`。

## 新训练使用的发音前端

训练和新检查点推理共用 Misaki 0.9.4。普通话使用 Kokoro v1.1 的中文前端，英语使用美式词典、spaCy 词性标注及 eSpeak NG 回退。双语输出转换为 tiny-voca 的音素 ID 和重音序列。本地推理与 Colab 安装同一组[前端依赖](requirements-misaki.txt)。中文和英文均保留已核实的上下文纠音。[全量音素标注](dataset/phonemes/misaki.jsonl) · [新版前端读音核验](docs/misaki-reading-evaluation.md)

## 在 Colab 训练和续训

![Vivian 训练流程：将中文、英文和句内混读录音与文本对齐，提取特征并训练单音色模型](docs/vivian-tts/assets/training.png)

1. 完成上述 Qwen3-TTS 生成步骤后，31,799 句对应 63,598 段录音。训练入口直接读取两份 Drive 合成结果，按原句 ID 关联新版标注。同一句的男女录音共享划分，对齐前分别有 59,640、1,958 和 2,000 段训练、验证、测试录音。
2. 在 Colab 选择 GPU 并运行[双播音员训练笔记本](notebooks/Announcers-Bilingual-Tiny-Voca.ipynb)。首次可将 `SMOKE = True`，从两种音色和三类语料各抽少量样本，训练 80 步并试听。笔记本自带训练源码，使用 Python 3.11、Torch/TorchAudio 2.8.0 和 Misaki。
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
