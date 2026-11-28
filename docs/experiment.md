# 双播音员训练配置与复现

## 语料规模

下表按句子 ID 统计仓库中的三个划分。每句话只属于一个划分。男、女播音员各合成一遍后，同一句的两段录音沿用原句划分，分别对齐。最后一行是全量配音完成后、强制对齐前的预期规模。[文本清单](../dataset/) · [录音配对脚本](../scripts/prepare_announcers.py)

| 单位 | 训练 | 验证 | 测试 | 合计 |
| --- | ---: | ---: | ---: | ---: |
| 普通话原句 | 19,658 | 241 | 160 | 20,059 |
| 英语原句 | 7,703 | 553 | 494 | 8,750 |
| 中英混读原句 | 2,459 | 185 | 346 | 2,990 |
| 全部原句 | 29,820 | 979 | 1,000 | 31,799 |
| 两种音色的录音（段） | 59,640 | 1,958 | 2,000 | 63,598 |

## 两份 Colab 笔记本之间如何传数据

1. 将仓库的 [tiny-voca-mix-colab-31799.zip](../data/tiny-voca-mix-colab-31799.zip) 放入 `MyDrive/tiny-voca-mix-qwen3-tts/downloads/`。打开仓库当前的[配音笔记本](../notebooks/Qwen3-TTS-VoiceDesign-Tiny-Voca-Mix.ipynb)，选择 GPU。笔记本从 ZIP 中提取完整原文和 Misaki 标注。
2. Qwen3-TTS VoiceDesign 根据两份描述和参考台词各生成一段参考音。Base 模型沿用对应参考音，分别朗读中文、英文及整句混读文本。勾选 `PREVIEW_ONLY` 可先检查两种音色各三类输入；全量运行时关闭此选项。默认合成批大小为 32，遇到显存不足可自动缩小批次。断线续跑时沿用相同的音色描述、参考音和生成配置。
3. 全量运行的最后一个单元将两份音频 ZIP 写入 `MyDrive/tiny-voca-mix/downloads/`。**另把第 1 步的输入 ZIP 复制到这个目录。** 打开仓库当前的[训练笔记本](../notebooks/Announcers-Bilingual-Tiny-Voca.ipynb)，它从以下三个包读取数据，在 Colab 本地磁盘解压后开始配对。

```text
MyDrive/tiny-voca-mix/downloads/
├── tiny-voca-mix-colab-31799.zip
├── tiny-voca-male-31799.zip
└── tiny-voca-female-31799.zip
```

每个音频包包含该播音员的 WAV、生成配置和清单。配对脚本校验原文清单哈希、标注指纹和每种音色的句子 ID。训练记录用 `sentence_id` 关联原句，录音 ID 加上 `male-` 或 `female-` 前缀。两个音色共享音素和重音，各有自己的帧级特征与音素时长。

## 特征提取与对齐

CPU 进程从 24 kHz 单声道录音提取基频、能量和 80 维 Mel 特征，帧移为 256 个采样点。GPU 将重采样至 16 kHz 的录音按批送入 MMS_FA，随后逐段定位中文音节和英文单词。每段录音的音素时长之和必须等于声学帧数。默认 `PREPROCESS_WORKERS = 4`、`ALIGN_BATCH_SIZE = 4`，两项可独立调整。[预处理实现](../scripts/preprocess.py)

每 128 段录音保存一个分块到 Drive 的 `tiny-voca-training/preparation/`。重跑可复用已完成的本地分块，或从 Drive 恢复。按划分保存的 `*.rejected.jsonl` 记录失败样本及原因。训练、验证和测试中，每种语言都须有至少 80% 的录音通过预处理。

## 试跑、全量训练与恢复

| 设置 | 小规模试跑 | 全量训练 |
| --- | --- | --- |
| 训练笔记本开关 | `SMOKE = True` | `SMOKE = False` |
| 对齐前样本 | 每种音色、每类语言取训练 8 段、验证 2 段、测试 2 段 | 全部配对录音 |
| 目标步数 | 80 | 104,000 |

两种模式均需先准备好三个完整 ZIP。默认 `SEED = 20261113`，每批最多 16 段，补齐后的总帧数最多 4,000。每 500 步保存续训状态，每 10,000 步保留一份快照。实际完成步数以运行日志和检查点为准。

输出位于 `MyDrive/tiny-voca-mix/tiny-voca-training/`。训练单元打印本次实验的检查点路径，并将日志写入 `logs/`。断线后用同一份数据、种子和训练配置依次重跑，训练单元会读取本次实验的 `checkpoints/last.pt`。生成语音使用同一目录下的 `inference.pt`。如末尾试听单元找不到文件，可在该单元中将 `checkpoint` 设为 `RUN / 'inference.pt'`，以沿用训练单元实际选定的目录。
