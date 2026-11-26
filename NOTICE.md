# 来源与许可范围

## 代码

语音模型、训练器、声学特征和推理逻辑源自 Muhammed Nazeem 的 tiny-voca，以及 xiaoliukuailiu 的普通话版本 tiny-voca-zh。Vivian 笔记本以 tiny-voca-zh 提交 `7ec7434bb052fcd6da8066e77f7d0e160586e095` 为底本，加入句内双语前端、单音色训练和混合文本对齐。仓库保留了随训练源码提供的 Apache License 2.0。[tiny-voca](https://github.com/n4ze3m/tiny-voca) · [tiny-voca-zh 底本](https://github.com/xiaoliukuailiu/tiny-voca-zh/tree/7ec7434bb052fcd6da8066e77f7d0e160586e095) · [许可证文本](LICENSE)

## 数据、音色与样音

- 中文文本来自 tiny-voca-zh 中文语料。英文文本来自 Muhammed Nazeem 发布的 tiny-voca 数据集，原训练清单保留逐条文本来源及已有许可字段。[tiny-voca-zh](https://github.com/xiaoliukuailiu/tiny-voca-zh) · [tiny-voca 数据卡](https://huggingface.co/datasets/n4ze3m/tiny-voca)
- 句内混读转写来自 Holy Lovenia 等人的 ASCEND。使用的是标为 mixed 的转写，音频由 Vivian 重新合成。原清单保留了所用转写的划分、行号及 CC BY-SA 4.0 许可记录。[ASCEND 论文](https://aclanthology.org/2022.lrec-1.788/) · [数据版本](https://huggingface.co/datasets/CAiRE/ASCEND/tree/b65b9bb) · [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
- 教师录音由 ElevenLabs 的 Vivian 音色与 `eleven_multilingual_v2` 生成。文中三段试听由训练得到的 104,000 步检查点生成。语料、音色、样音和模型权重的使用及分发条件需按各自来源与适用协议核对。代码许可仅用于相应代码。[ElevenLabs 使用政策](https://elevenlabs.io/use-policy)


## 浏览器推理

网页通过 ONNX Runtime Web 1.20.1 运行 Vivian，由 Pyodide 0.26.4 执行本项目的双语文本前端。拼音与数字读法使用 pypinyin 0.55.0 和 num2words 0.5.14。英文音素来自 Spellophone 0.2.1 打包的 eSpeak NG。构建时从各软件的原版发行包提取所需文件。[ONNX Runtime](https://github.com/microsoft/onnxruntime) · [Pyodide](https://github.com/pyodide/pyodide/tree/0.26.4) · [pypinyin](https://pypi.org/project/pypinyin/0.55.0/) · [num2words](https://pypi.org/project/num2words/0.5.14/) · [Spellophone 发行包与源码](https://www.npmjs.com/package/@spelling-creator/spellophone/v/0.2.1)
