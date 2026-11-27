# Vivian 双语前端读音核验

## 结果

评测从完整原句调用生产前端，按位置比较一个指定字或词的输出。随机抽样使用训练资料中的 test 划分；每句只有一个目标。三类等量抽样的精确参考命中率为 **117/120（97.5%）**。

| 评测集 | 保留项目纠音的 Misaki | 初版 Misaki 适配（未启用项目纠音） |
|---|---:|---:|
| 随机纯中文，声韵母和声调 | 40/40 | 40/40 |
| 随机纯英文，整词音段 | 37/40 | 37/40 |
| 随机中英混合，20 个汉字和 20 个英文词 | 40/40 | 40/40 |
| 历史中文多音字专项，含纯中文及混合句 | 861/862 | 42/862 |
| 历史英文词音专项，含纯英文及混合句 | 84/84 | 53/84 |
| 历史英文主重音专项，含纯英文及混合句 | 17/17 | 未测 |

**随机样本的三处差异均在英文。** 在 “the ancient oak tree” 中，前端读 /ði/，符合元音前常见读法；初始参考只列了 /ðə/。在 *nobody* 中，前端输出符合 Cambridge 所列美式音。在 *significant* 中，两处非重读元音的转写有差异。表中保留测试前冻结的判据和统计，以便复现。前两处说明转写失配也可能是参考遗漏了可接受的变体。[Cambridge 对 nobody 的注音](https://dictionary.cambridge.org/pronunciation/english/nobody) · [Cambridge 对 significant 的注音](https://dictionary.cambridge.org/pronunciation/english/significant)

英文词音专项检查 live、read、use、close 在原句中的读法；主重音专项另选取了 graduate、project、present 等词。

中文专项中的 401 处“长”和 381 处“数”在最终前端均符合参考。剩余差异出现在混合句“那得好几百个人”的“得”。前端输出 déi，既有参考标为 děi，二者选定的词义相同，连续三声的分组有差异。

## 参考读音和覆盖范围

随机集按语言从不含阿拉伯数字、英文撇号或连字符的 test 句中抽取，每类 40 条。随机种子为 72，每句从汉字和英文字词中抽取一个目标；混合句交替抽取两种语言。参考音由本次评测的 agent 阅读上下文后独立填写，填写时未查看新前端输出。参考记录只保存样本 ID、位置、字词和预期读音。

中文比较完整声韵母和调号；英语音段评分容许参考文件所列变体，并统一元音长短等少量转写惯例。17 个单独的英语主重音目标按第几个元音承载主重音评分。随机集的英语分数未纳入重音。专项参考来自项目此前的文本审查和计数用法规则，集中覆盖已知难例且含重复句型，用于回归验证。两类结果不合并为全库准确率。这里核验文字读音，未听审 Vivian 录音，也未判定样本中其余字词是否全部正确。

## 复现

安装项目的 Misaki 依赖后，从仓库根目录运行。输入需包含完整中文正文，默认使用本地 Qwen 输入清单。指定 `--annotations` 时另逐句核对落盘的音素与重音。

```sh
PYTHONPATH=src python scripts/evaluate_readings.py \
  data/tiny-voca-mix-qwen3-tts/inputs/corpus.jsonl \
  --annotations dataset/phonemes/misaki.jsonl \
  --output /tmp/vivian-reading-results.jsonl
```

最终标注指纹为 `85c0f8170fc3ea39f59ec8e089740aac5064c7f079466d83b7b805abf2ef3d0e`。已按完整清单重新生成 31,799 条标注。逐句与全量审查时冻结的新版输出核对，音素、编号和重音全部一致。

四组冻结的参考位于 `tests/fixtures/misaki-*-references.jsonl`。结果中每一项保留原 ID、目标、期望读音、实际得分及通过状态。

本地逐项目标及判定保存在 [runs/misaki-reading-results.jsonl](../runs/misaki-reading-results.jsonl)，筛选 `"passed": false` 可找到与参考不一致的项目。
