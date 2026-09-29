# 小狼毫本地颜文字推荐

默认直接在小狼毫内运行，不需要启动 Python 服务、命令窗口或联网。现有 **918 个去重颜文字、40 个动作/动物/物品主题、864 条情绪触发短语**。

## 现在怎么用

支持前缀联想：只输入“抱”“咖”“晚”“生日快”“摸摸”“笑不活”等开头，也能提前看到相关颜文字；例如“我想喝咖”会联想到咖啡。候选注释显示“联想：咖啡”等完整触发词。选择后保留你已输入的中文并追加颜文字，不会擅自补写汉字。完整匹配优先，泛义单字和否定前缀会过滤。

1. 正常输入中文拼音，候选栏前 3 项保留中文，后面直接显示 6 个相关颜文字候选。
2. 想指定同音字：用 ↑ / ↓ 高亮你想要的中文候选，按 **F8**。展开候选会绑定这个中文，最多 36 个，使用 **PageDown / PageUp** 翻页，数字键选择。上屏内容为“选中的中文 + 颜文字”。不要先按数字选中文字，否则它会直接上屏。
3. 中文已经上屏：30 秒内按 **F8**，只补颜文字，不重复中文。
4. **F9** 暂时开关推荐；**Shift+F9** 清除当前会话记忆与缓存。重启输入法后默认开启。
5. 展开后再按 F8 可返回普通候选；修改拼音会解除之前锁定的中文。

例如输入“抱抱、亲亲、摸摸头、吃饭、晚安、学习、开黑、猫、狗狗、熊猫、蛋糕、咖啡、鲜花、下雨”，可获得相应动作或图案。情绪覆盖日常表达、网络用语、否定、转折、救命/呵呵等歧义场景。

每个主题的实际数量不同，最多 36 个并不代表每个词都有 36 个。词库总量是 918 个，系统按相关性筛选。

## 安装或更新

需要小狼毫支持 librime-lua；已验证官方小狼毫 0.17.4 和朙月拼音简化字 `luna_pinyin_simp`。安装脚本需要 Python 3.11+、PyYAML、lupa；日常输入无需 Python。

在项目目录运行：

```powershell
python -m pip install -r requirements.txt
python scripts/install_rime.py --user-dir "$env:APPDATA\Rime" --schema luna_pinyin_simp
```

用户目录以小狼毫托盘“用户文件夹”为准。安装器保留已有配置，遇到冲突会停止，写入前生成 `.kaomoji-backup-日期时间` 备份。随后在小狼毫托盘菜单点一次“重新部署”。更新后无需每天重新打开插件。

手工安装需复制 `rime/kaomoji.lua`、`rime/kaomoji_local.lua`、`rime/kaomoji_data.lua` 到用户目录 `lua` 文件夹，将 `rime/rime.lua.snippet` 合并到 `rime.lua`，将 `rime/example.custom.yaml` 的 patch 合并到当前方案配置。不要直接覆盖已有其他插件配置。

## 调整数量

当前方案的 `.custom.yaml` 中：

```yaml
patch:
  "kaomoji/auto_count": 6
  "kaomoji/expanded_count": 36
  "kaomoji/insert_after": 3
  "menu/page_size": 9
```

自动数量允许 1–12，展开数量允许 6–64，修改后重新部署。自动候选分析首选中文；F8 展开才绑定当前高亮中文。输入法无法读取其他应用中任意光标周围的文字。

## 扩充字库和触发词

- `data/collections.json`：颜文字及动作/名词主题。
- `data/lexicon.json`：中文触发词、否定规则和情绪权重。
- `scripts/build_offline.py`：合并原始词库、去重、生成 Python 数据和本地 Lua 数据。

```powershell
python scripts/build_offline.py
python -m pytest -q
```

生成后重新运行安装器并部署。不要单独运行旧 `build_demo_data.py` 更新发行词库，它只生成基础数据。

## 可选 Python API

开发调试时可运行 `python python/server.py`，地址 `http://127.0.0.1:8765`。`POST /recommend` 接收 `text`、`top_k`（1–64）、可选 `context` 和 `recent`。默认 API 返回 3 个是兼容旧客户端的设置，小狼毫默认返回 6 个。

Python 保留更丰富的解释分数、上下文分析和旧文件桥接接口；默认小狼毫使用本地 Lua，不读取该服务的结果。两者共享词库与扩展短语，排序与特殊语境细节可能不同。默认不记录输入文本，不调用云服务。

## 验证与限制

220 项自动测试通过；真实官方小狼毫 DLL + 完整拼音词库通过无需服务、六个候选、同音候选锁定、分页、数字键上屏和 F9 开关测试。见 `docs/verification.md` 与 `docs/weasel-pinyin-smoke.json`。

识别仍然基于可解释规则，不是大语言模型；复杂反话、长距离指代可能误判。动作和名词命中会优先检索对应主题。原生测试为隔离引擎测试，不代表已逐一验证 Windows 应用窗口和字体兼容性。
