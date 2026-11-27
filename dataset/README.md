# 双语文本清单

每行对应一句，供不同音色共用。共 31,799 条，其中中文 20,059 条、英文 8,750 条、中英混读 2,990 条。

| 训练集 | 验证集 | 测试集 |
| --- | --- | --- |
| [29,820 条](train.jsonl) | [979 条](validation.jsonl) | [1,000 条](test.jsonl) |

沿用原有 26,910 条的划分，新增 4,889 条英文按上游划分并入。男声与女声合成时均沿用同一句的 `id` 和 `split`。本目录的纯中文记录仅提供标识和划分。[Colab 输入包](../data/tiny-voca-mix-colab-31799.zip) 包含三类文本的完整正文。

## 文本来源与使用条件

- 中文样本来自 tiny-voca-zh。现有来源说明未明确中文句子的再分发许可。[中文项目](https://github.com/xiaoliukuailiu/tiny-voca-zh)
- 英文句子来自 Muhammed Nazeem 的 tiny-voca dataset，覆盖两个批次。每条记录的 `text_source` 保留上游句子 ID、来源与许可标记。[上游数据集](https://huggingface.co/datasets/n4ze3m/tiny-voca) · [上游许可与第三方署名](https://huggingface.co/datasets/n4ze3m/tiny-voca/blob/main/LICENSE.md)
- 中英混读转写选自 Holy Lovenia 等人的 ASCEND，按 CC BY-SA 4.0 提供。本项目选取混读文本并加入 Vivian 样本信息；每条转写的原始划分与记录编号见 `text_source.records`。[ASCEND 数据版本](https://huggingface.co/datasets/CAiRE/ASCEND/tree/b65b9bb) · [论文](https://aclanthology.org/2022.lrec-1.788/) · [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)

## Misaki 音素标注

[全量标注](phonemes/misaki.jsonl) 按本地完整文本清单的顺序逐行保存，使用 `id` 与上面的三个划分关联。每行包含项目音素字符串 `symbols`、对应的模型输入编号 `tokens`、逐音素重音 `stress` 以及生成前端的 `frontend` 指纹。拼音韵母的数字表示声调。安装项目的前端依赖后，在仓库根目录运行以下命令可重新生成。

```sh
PYTHONPATH=src python scripts/annotate_corpus.py \
    data/tiny-voca-mix-qwen3-tts/inputs/corpus.jsonl dataset/phonemes/misaki.jsonl
```

新训练由 Qwen3-TTS 的男女播音员各读全部 31,799 句。两份录音共享原句的音素和重音，训练预处理逐条与实时 Misaki 输出核对，再为每段录音单独计算音素时长。
