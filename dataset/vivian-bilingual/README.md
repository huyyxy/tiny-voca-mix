# Vivian 双语训练清单

清单来自 Vivian 的 ElevenLabs 教师录音训练包。每行是一条样本。按语言统计，共有 20,059 条中文、3,861 条英文和 2,990 条中英混读样本。

| 划分 | 文件 | 样本数 |
| --- | --- | ---: |
| 训练 | `train.jsonl` | 25,592 |
| 验证 | `validation.jsonl` | 619 |
| 测试 | `test.jsonl` | 699 |

`corpus.jsonl` 汇总这三个划分，共 26,910 条。用 `id` 定位录音，用 `text_id` 比对文本。路径 `audio` 相对于原训练包根目录，`audio_sha256` 可用于核对已有录音。中文记录省略了 `text` 字段，其余字段沿用原清单。

## 文本来源与使用条件

- 中文样本来自 tiny-voca-zh。现有来源说明未明确中文句子的再分发许可，因此公开版仅提供元数据。[中文项目](https://github.com/xiaoliukuailiu/tiny-voca-zh)
- 英文句子选自 Muhammed Nazeem 的 tiny-voca dataset。3,287 条来自 Mozilla Common Voice（CC0 1.0），574 条为上游项目自写模板（标记为 `project-own`，上游数据集采用 CC BY 4.0）。逐条出处见 `text_source`。[数据集与署名](https://huggingface.co/datasets/n4ze3m/tiny-voca) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- 中英混读转写选自 Holy Lovenia 等人的 ASCEND，按 CC BY-SA 4.0 提供。本项目选取混读文本并加入 Vivian 样本信息；每条转写的原始划分与记录编号见 `text_source.records`。[ASCEND 数据版本](https://huggingface.co/datasets/CAiRE/ASCEND/tree/b65b9bb) · [论文](https://aclanthology.org/2022.lrec-1.788/) · [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
