# Phase 4：可选本地 NLP 设计

当前交付是已验证的规则 MVP。没有现成模型被假装成这 22 个情绪、14 个意图和多语气的可靠分类器。现有预训练 encoder 是表征模型，需要针对中文聊天标注和训练分类头。

## 方案比较

表中速度是相对预期，尚未在目标 RTX 3050 笔记本实测；不声称某个未经运行的模型能满足 50 ms。实际应按 batch=1、长度 64/128 字、热启动和 P95 测量。

| 方案 | 延迟 / CPU | 模型大小 | 中文口语能力 | 部署与训练 |
|---|---|---|---|---|
| 规则 | 已测亚毫秒分析，CPU 足够 | 小 JSON，无权重 | 显式俚语、标点、否定可解释；反语和新词需维护 | 最易部署，无训练数据；保留为所有失败时的默认后端 |
| 字符 TF-IDF + 线性分类 | 通常适合低延迟 CPU，需实测词表规模 | 跟词表和类别数线性增长，通常显著小于 base encoder | 中文字符 n-gram 对口语和新词片段实用；长语境和反讽有限 | 增加 scikit-learn，标注数百至数千条起步，类别平衡与领域覆盖更重要 |
| Chinese BERT base | batch=1 比线性模型重；CPU 需优化 | base encoder 通常数百 MB 浮点权重，INT8 可减小 | 通用中文语义较强，但“呵呵”“寄”不能凭名称保证正确 | transformers/tokenizer + 训练头/ONNX，需多标签训练集 |
| 中文 RoBERTa-wwm-ext | 同级 base 与 BERT 资源量接近 | base 仍是较大权重 | 全词掩码预训练；聊天适应性要用相同留出集比较 | 部署与 BERT 相近，不能用三分类情感模型替代所需标签 |
| MacBERT base | 同级 base，CPU P95 要测 | base 权重，不是小模型 | 其中文预训练策略值得作为 encoder 对照，不能保证俚语理解 | 有可用中文预训练权重，但仍需多任务标注/微调 |
| MiniLM / 小 embedding encoder | 较小层宽可能改善运算，但词表和长度仍影响 CPU | 多语言 MiniLM 的大词表可占很大部分参数；名字“小”不等于文件必然更小 | 支持中文的模型可做检索/分类特征；日常聊天和情绪需评估 | 必须选择实际支持中文的 tokenizer / model，冻结 embedding + 线性头容易起步 |

模型与结构依据：[Chinese BERT 模型卡](https://huggingface.co/google-bert/bert-base-chinese)、[中文 RoBERTa-wwm-ext 模型卡](https://huggingface.co/hfl/chinese-roberta-wwm-ext)、[MacBERT 模型卡](https://huggingface.co/hfl/chinese-macbert-base)、[多语言 MiniLM 模型卡](https://huggingface.co/microsoft/Multilingual-MiniLM-L12-H384)。TF-IDF 实现依据 [scikit-learn 文本特征文档](https://scikit-learn.org/stable/modules/feature_extraction.html#text-feature-extraction)。表中的相对部署取舍和数据量起点是工程建议。

## 选择

首先保留规则。下一阶段优先做 **字符 TF-IDF（1～3 gram）+ 线性多任务头**，用同一套 JSON 输出喂给现有 ranker。它适合 CPU，易测量，也能判断是否值得加入 encoder。

若模型确实改善留出集上“呵呵”“救命”“麻了”、否定和转折的识别，再考虑中文小 encoder 或 MacBERT 对照。普通 16 GB RAM 足够做此类推理；RTX 3050 可用于微调/对照，但默认仍是 CPU。GPU 显存与驱动差异需要单独验证，不把 CUDA 作为安装前提。

## 标注与训练

每条训练数据保存当前话语、允许的最近语境、22 个 emotion 的多标签、14 类 intent、6 个 tone 多标签和 0～1 intensity。应允许 unsure 标志，不强行把“救命”归成单一情绪。

建议先收集每个类别约 100～300 个独立例子作为起点，再根据混淆矩阵补充；这不是准确率保证。保持稀有类别、否定、程度、emoji 和俚语的覆盖。现有 107 条测试句只是工程回归集，不能同时作为训练集和模型准确率证据。用户数据采集必须主动授权，默认服务仍不记录原文。

按会话/来源分割训练、验证、测试，避免相似改写泄漏。评估 multi-label macro F1、每类 precision/recall、intent macro F1、tone F1、intensity MAE，以及最终 Top-K 的人工适合度和不合适推荐率。

encoder 后接 emotion sigmoid、tone sigmoid、intent softmax、intensity regression 四个轻量头。类别不平衡采用加权损失与验证集阈值，不把每个情绪都当成互斥类别。可把明确的规则证据与模型分数融合，风险较高的“救命 + 危险语境”不应被幽默规则无条件覆盖。

## 部署与 CPU fallback

冻结标签版本与 tokenizer，模型包清单记录训练领域、校准阈值、校验和及许可证。可导出 ONNX，先用 CPUExecutionProvider，测试动态量化；量化影响与兼容性遵循 [ONNX Runtime 官方文档](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)。只有真实 benchmark 支持时才承诺 <50 ms；100 ms 以上则撤回结果并继续中文输入。

服务应使用独立、可终止的推理进程，并限制待处理请求为最新值。主 worker 等待时间最多 100 ms，加载失败、超时或模型异常回退规则。仅在后台执行模型；Lua 仍只发文件请求和读结果。CPU fallback 应在启动时检测 backend，在 GPU 不可用时选 CPU，CPU 仍无法达标时选规则。现有 `RecommendationService` 是接入点，当前尚未实现这些模型依赖和训练程序。
