# 网络颜文字来源与导入记录

本次从公开网络数据集中导入，不需要使用者联网搜索，也不会在输入时访问网站。

## 来源

- 项目：[kaomojikan/kaomoji-data](https://github.com/kaomojikan/kaomoji-data)。
- 固定版本：[60c92ea4e85279ad42ff525e9a40464ebeb1003e](https://github.com/kaomojikan/kaomoji-data/tree/60c92ea4e85279ad42ff525e9a40464ebeb1003e)。
- 获取日期：2026-09-29。
- 许可：MIT，版权归原作者 kaomojikan；[原许可全文](../data/upstream/kaomojikan/LICENSE)。
- 原始数据：[本地版本快照](../data/upstream/kaomojikan/kaomoji.json)。
- 文件哈希、拒绝原因及统计：[web_sources.json](../data/web_sources.json)。

原始数据和许可随仓库保留；生成的小狼毫数据文件也内嵌原许可。未复制网页介绍文章或用户评论。

## 处理方式与结果

原始数据 1,808 条；过滤多行/控制字符、不适合单行候选栏的 AA 类、缺少可映射含义的条目，并做 Unicode NFKC 与空白规范化去重，得到 1,563 条待合并数据。再与原有 977 个颜文字去重，新增 **1,401 个**，最终 **2,378 个**。

保留图案原文与内部空格，不把多行图强行拼成一行。日文标签按人工编写的映射表转换为本项目情绪及主题；不是机器逐条理解图案，少数表达可能有语义差异。部分原始图案包含日文短语或 emoji。

补充了猫、狗、兔、熊、摸头、偷看、吃饭、睡觉、拥抱等已有类别；新增可爱、扔东西、倒地、追星、吐舌头、仓鼠主题，现有主题共 50 类。仓鼠来自这批数据的可用条目较少，不保证每个类别都有 36 个推荐。小熊猫与海獭保留项目之前独立整理的分类，不把普通熊冒充小熊猫。

完整匹配、前缀联想、F7 只输出颜文字、F8 绑定所选中文和分页方式保持原有操作。

## 离线复现

在项目目录执行：

```powershell
.\.venv\Scripts\python.exe scripts\import_web_kaomoji.py
.\.venv\Scripts\python.exe scripts\build_offline.py
.\.venv\Scripts\python.exe -m pytest -q
```

导入脚本读取仓库中的固定快照，不会自动下载或执行上游脚本。`data/web_collections.json` 是转换后的网络词库；`data/collections.json` 保留项目自行整理的原有词库。每条实际入库的网络数据有 `source` 和 `source_id`，可追溯到原始记录。
