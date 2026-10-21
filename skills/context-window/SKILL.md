---
name: context-window
description: GPT专属。在Windows本地ChatGPT Work/Codex中调整全部或指定模型的上下文窗口、有效比例和自动压缩阈值，查询配置、刷新模型目录并备份恢复。不用于单会话、普通Chat云端或其他客户端。
metadata:
  version: 0.4.0
---

# 上下文设置（GPT专属）

只操作本机OpenAI Codex配置。用户用自然语言指定参数，助手执行，无需旧聊天记录。安装、维护技能不授权修改实际设置；收到明确调整指令才写入配置。不自动关闭应用。

## 范围与参数

| 用户意思 | scope | model |
|---|---|---|
| 本机全局，全部模型 | global-all | 不填 |
| 本机全局，只改指定模型 | global-model | 当前目录中的精确模型id |

仅提供这两种全局范围，不做单会话调整。范围不明时只询问范围；模型别名从当前目录核对，不能把Sol硬编码为某一代。

| 参数 | CLI选项 | 语义 |
|---|---|---|
| 原始窗口 | --tokens | 正整数、60万、600k、1M；省略/keep保持现状 |
| 有效比例 | --effective-percent | 1—100整数，可带%；省略/keep保持现状 |
| 自动压缩阈值 | --auto-compact-limit | token数、default恢复当前模型默认、keep保持现状（默认） |

只改用户提到的参数，不反复索要三项值，不预填372K或95%。支持仅改比例、仅改压缩或三项一起改。“60万”就是600000原始token，不自动除以比例；用户明确要求可用窗口时先说明换算。有效窗口和压缩阈值是不同概念。

## 调用

终端使用PowerShell 7。`scripts/context_window.py`仅依赖Python 3.11+标准库，复用已有Python，不重新安装。先用`status`核对当前目录、全局覆盖、上限、比例、压缩与计数范围。脚本相对技能目录调用；先确认可用的Python 3.11+解释器，不依赖作者机器上的路径。

示例（python须指向已确认的3.11+解释器；模型id需先核对）：

```powershell
python scripts/context_window.py status
python scripts/context_window.py set --scope global-model --model gpt-6.1-sol --tokens 60万 --effective-percent 95 --auto-compact-limit 50万 --preview
python scripts/context_window.py set --scope global-model --model gpt-6.1-sol --tokens 60万 --effective-percent 95 --auto-compact-limit 50万
python scripts/context_window.py set --scope global-model --model gpt-6.1-sol --effective-percent 90
python scripts/context_window.py set --scope global-all --auto-compact-limit default
```

`--home`位于子命令前，可指定隔离配置目录；默认遵守CODEX_HOME，否则使用用户的`.codex`。`--preview`不写配置、目录或备份，仅可能建立短暂锁目录。明确的修改指令已授权对应写入，不额外要求用户批准预览。

## 配置配合与限制

- 全部模型：窗口、显式压缩阈值使用config.toml顶层配置；有效比例写入独立模型目录各条目，并记录为全部模型选择，刷新时也应用于新加入的模型。
- 指定模型：仅在独立目录中修改所选参数；不修改max_context_window、不动模型缓存、认证和无关字段。
- 全局窗口/压缩覆盖遮住指定模型时，仅将本次需调整的那个参数折入各模型，再移除对应顶层覆盖。说明该转换，保留其他模型原有效数值。只改比例不会顺带搬移窗口或压缩。
- 若显式全局压缩采用body_after_prefix计数，无法无损转为单模型条目，脚本停止；解释冲突，不擅自改成total。只修改阈值不顺带改变计数范围。
- 恢复默认压缩：从本机models_cache.json取得当前模型默认字段（未提供时移除自定义字段），清除对应范围的记录。全局恢复还移除顶层压缩阈值及计数范围覆盖。缓存缺失或缺少目标模型时停止，不猜默认；可先用本机debug models核对来源。
- 目录max_context_window仍会限制请求窗口。预计可用窗口=预计原始窗口×有效比例。当前客户端的压缩阈值还受原始窗口90%限制。新指定的显式阈值不得超过90%窗口或可用窗口；冲突则不写入并报告具体允许值。仅改窗口/比例时保留既有压缩设置，报告可能的限制，不静默调整。
- 不将本地元数据调整宣传为突破服务端能力。预计值可能被profile、受管策略或保留启动配置的进程覆盖。

## 模型资料刷新

现有自定义目录由本技能管理时，`refresh`预览、`refresh --apply`应用。支持三种来源：

```powershell
# 本机已获取的模型资料（默认）
python scripts/context_window.py refresh
# 当前已安装Codex附带的内置资料
python scripts/context_window.py refresh --refresh-from-bundled
python scripts/context_window.py refresh --refresh-from-bundled --apply
# 已核对的JSON目录
python scripts/context_window.py refresh --source C:\path\models.json
```

内置来源使用已有`codex debug models --bundled`；找不到命令时用`--codex`指定本机已有可执行文件绝对路径，不下载。该选项只与`--refresh-from-bundled`同用，且不能与`--source`混用。内置资料和账户缓存可能不同；内置目录不是账号权限证明，也不保证比缓存更新。

预览展示新增、移除模型、未覆盖的默认参数变化、保留的自定义参数和来源。刷新完整采用新模型字段，再叠加有记录的窗口/比例/压缩选择；无覆盖的参数跟随新版资料。单模型选择优先于全部模型比例。新版缺少自定义模型或压缩设置变得不适用时停止，不丢选择。

兼容0.3.0备份的desired_windows，仅迁移已记录窗口，不猜比例和压缩。目录哈希与记录不匹配时停止刷新。仅设置顶层全局窗口/压缩且无本技能目录时无需刷新，不能假装已执行。

## 恢复与结果

写前备份、并发锁、原子写入及失败回滚沿用原机制。`restore <backup_manifest>`恢复指定事务；当前文件或备份SHA-256不匹配则停止，避免覆盖后续更改。旧版备份继续可用。

输出简短说明：范围、模型、实际修改的参数、预计可用窗口和压缩限制、已保存/已生效、是否需重新加载。`saved_requires_reload`只代表已保存；`status`及预览均不证明运行生效。运行窗口需核对目标聊天最新`token_count.info.model_context_window`或采样日志；没有压缩运行证据就不声称压缩阈值已生效。

依据：[官方配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)、[官方模型元数据与限制实现](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/openai_models.rs)。参数界面与内置刷新选项参考[smartcmd/codex-context-window](https://github.com/smartcmd/codex-context-window)，保留本技能两种范围、修改记录和校验恢复机制。
