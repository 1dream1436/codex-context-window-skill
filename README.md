# Codex Context Window Skill — ChatGPT Work Local & Codex Local

[![CI](https://github.com/1dream1436/codex-context-window-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/1dream1436/codex-context-window-skill/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Windows x64 standalone](https://img.shields.io/badge/Windows-x64_standalone-blue)

在 Windows 本地 ChatGPT Work / Codex 中，用自然语言调整上下文窗口、有效比例和自动压缩阈值。支持全部模型或指定模型、模型资料刷新、预览、备份与恢复。**Windows x64 发布包内置独立程序，无需安装 Python 或配置虚拟环境。**

**Configure the context window token limit, effective context percentage, and auto-compaction threshold in Windows ChatGPT Work Local and Codex Local using an installable agent skill.** Apply settings to all models or one selected model, preview changes, refresh the model catalog, and back up or restore configuration. **The Windows x64 release includes a standalone executable; no Python setup is needed.**

[English guide](#english-guide) · [中文说明](#能做什么) · [FAQ / 常见问题](#faq--常见问题)

**双界面验证 / Verified in both desktop modes:** 500K raw → 475K effective and 600K raw → 570K effective at 95%. These are observed local configuration results, not a guarantee of server-side capacity or long-input performance. See [validation evidence and reproduction steps](docs/VALIDATION.md#work-local-与-codex-local-双界面验证).

## English guide

### What this skill configures

This unofficial OpenAI Codex agent skill manages the shared local Codex configuration used by **ChatGPT Work Local** and **Codex Local** on Windows. Use natural-language requests or the bundled command-line executable to change:

- **Context window / token limit** (`--tokens`): configure the raw context size, for example `500k` or `600k`, subject to the current model catalog and client limits.
- **Effective context percentage** (`--effective-percent`): set the percentage used to calculate the client's expected usable context window.
- **Auto-compaction / automatic context compression threshold** (`--auto-compact-limit`): choose when the client should attempt context compaction, or restore the model default.
- **Global or per-model settings**: target all models (`global-all`) or one exact model ID (`global-model`), while preserving unspecified parameters.
- **Model catalog refresh, preview, backup and restore**: refresh metadata from the local cache, installed Codex bundled catalog, or a supplied JSON file; preserve recorded custom choices and check for conflicting changes before writing.

Related configuration terms include `config.toml`, `model_context_window`, `model_auto_compact_token_limit`, and `context_window` model metadata. The skill handles the configuration changes rather than requiring users to edit these files manually.

### Desktop verification and scope

In the documented Windows test, new chats opened from both ChatGPT Work Local and Codex Local used 475K effective context for a 500K raw setting and 570K for a 600K raw setting. The test used a 95% effective percentage and Codex engine `0.163.0-alpha.11`. Both modes read shared user settings when the model, configuration directory, and overrides match; the skill does not store separate window sizes for Work and Codex modes.

The desktop test verifies context-window values in real runtime records. It does not establish that every model supports those sizes, that old chats update automatically, or that both desktop interfaces have separately passed compaction-threshold tests. Earlier engine tests observed automatic compaction; see [validation scope](docs/VALIDATION.md) for the distinction.

This is a community project, not affiliated with OpenAI. Local settings do not increase server-side model capacity or grant access to models. Regular cloud Chat mode, other clients, and per-conversation configuration are outside this project's scope.

### Requirements and installation

Use Windows x64 and an existing local ChatGPT Work / Codex environment. **The Windows release ZIP includes a standalone executable: no separate Python installation, virtual environment, third-party Python packages, or PowerShell 7 is required.** Use your existing terminal; the agent invokes the bundled executable.

Download the skill ZIP from [Releases](https://github.com/1dream1436/codex-context-window-skill/releases) and copy its `context-window` folder into the skill directory supported by your client, usually `.agents/skills` under your user directory. Some installations also recognize `.codex/skills`. Install only one copy, reload skills or open a new chat, and confirm that `$context-window` is available. Choose `context-window-0.4.1-windows-x64.zip` for installation without Python. Git source checkouts do not include generated executables; source developers may use an existing Python 3.11+ runtime instead.

### Usage examples

Ask your agent:

```text
Use $context-window to inspect my current context window settings.
Set only the selected model's context window to 600k; keep other settings unchanged.
Set the effective context percentage to 90% for all models.
Restore the selected model's default auto-compaction threshold.
Preview a model catalog refresh from my installed Codex bundled metadata.
```

Or run from the installed `context-window` folder, replacing `MODEL_ID` with an exact ID returned by `status` (PowerShell path syntax shown):

```powershell
.\bin\context_window.exe status
.\bin\context_window.exe set --scope global-model --model MODEL_ID --tokens 600k --preview
.\bin\context_window.exe set --scope global-model --model MODEL_ID --tokens 600k
.\bin\context_window.exe set --scope global-all --effective-percent 90
.\bin\context_window.exe set --scope global-model --model MODEL_ID --auto-compact-limit default
.\bin\context_window.exe refresh --refresh-from-bundled
.\bin\context_window.exe restore "PATH_TO_BACKUP_MANIFEST"
```

`--home PATH` goes before the subcommand and selects an isolated configuration directory. Otherwise, the script uses `CODEX_HOME`, falling back to `.codex` under the user directory. `refresh` previews by default; add `--apply` to save a refresh. Bundled refresh requires an installed Codex supporting `debug models --bundled`.

A result of `saved_requires_reload` means the configuration was saved. Open a new chat or reload as appropriate, then inspect actual runtime records to verify the effective context size. `status` and previews are estimates, not proof that a running chat has applied a setting.


这是社区项目，与 OpenAI 无隶属关系。修改的是本机 Codex 配置；普通 ChatGPT 云端聊天、其他客户端和单会话设置不在本项目范围内。

## 能做什么

- 分别调整窗口大小、有效比例和自动压缩阈值，只修改明确指定的参数。
- 对全部模型生效，或只调整当前目录中的一个精确模型 ID。
- 从本机缓存、已安装 Codex 的内置资料或指定 JSON 刷新目录，并保留已记录的自定义选择。
- 写入前备份，检查哈希，遇到冲突时停止；支持按事务恢复。
- Windows x64发布包内含独立运行程序，无须另装Python、创建虚拟环境或安装第三方包。

## 安装

需要Windows x64及已有的本地ChatGPT Work / Codex环境。下载 `context-window-0.4.1-windows-x64.zip` 后解压安装，助手直接调用包内的 `bin/context_window.exe`。**无须额外安装Python或PowerShell 7，也无须配置虚拟环境。**

Git源码版不含生成的EXE；源码开发者可复用已有Python 3.11+运行脚本。没有运行时的普通用户请使用Windows发布包。以下克隆安装方式适用于源码使用者；推荐普通用户直接下载发布包。

从 [Releases](https://github.com/1dream1436/codex-context-window-skill/releases) 下载技能 ZIP，将其中的 `context-window` 文件夹放入你的技能目录。也可以克隆仓库：

```powershell
git clone https://github.com/1dream1436/codex-context-window-skill.git
Set-Location codex-context-window-skill
$skillRoot = Join-Path $HOME '.agents/skills'
New-Item -ItemType Directory -Force $skillRoot | Out-Null
$target = Join-Path $skillRoot 'context-window'
if (Test-Path $target) { throw 'Skill already exists. Back it up and review before replacing.' }
Copy-Item -Recurse './skills/context-window' $target
```

`.agents/skills` 是官方文档列出的用户技能目录；某些本地安装也识别 `.codex/skills`。本项目最初实测使用后者。使用你的客户端实际支持的目录，避免同时安装两份同名技能。安装后重新加载技能或新开聊天，确认能找到 `$context-window`。安装技能本身不会修改上下文配置。

## 用自然语言操作

```text
使用 $context-window，查询当前模型的上下文配置。
只把指定模型的上下文窗口设为60万，其他参数保持不变。
把全部模型的有效比例设为90%。
把指定模型的自动压缩阈值恢复为默认。
从本机Codex内置资料刷新模型目录，先给我预览。
```

“60万”表示 600000 个原始 token。有效比例决定客户端预计可用窗口；压缩阈值决定何时尝试整理上下文，两者含义不同。模型 ID 从当前 `status` 输出核对，不根据别名猜测。

## 直接使用命令

以下命令在已安装的 `context-window` 目录执行（PowerShell路径写法）；`MODEL_ID` 需替换为当前目录中的精确 ID，数值仅作示例，并非适用于全部模型。

```powershell
.\bin\context_window.exe status
.\bin\context_window.exe set --scope global-model --model MODEL_ID --tokens 600k --effective-percent 95 --auto-compact-limit 500k --preview
.\bin\context_window.exe set --scope global-model --model MODEL_ID --tokens 600k --effective-percent 95 --auto-compact-limit 500k
.\bin\context_window.exe set --scope global-all --auto-compact-limit default
.\bin\context_window.exe refresh --refresh-from-bundled
.\bin\context_window.exe refresh --refresh-from-bundled --apply
.\bin\context_window.exe restore "PATH_TO_BACKUP_MANIFEST"
```

`--home PATH` 放在子命令之前，可在隔离目录操作；省略时使用 `CODEX_HOME`，未设置则使用用户目录下 `.codex`。需要内置刷新时，已有 Codex 必须支持 `debug models --bundled`；不在 PATH 中可加 `--codex` 指定现有程序。

## 生效与限制

`saved_requires_reload` 表示已保存。需要通过新聊天或重新加载后的实际运行记录确认生效；已打开的旧聊天可能仍持有旧设置。本技能不会自动关闭应用。`status` 和预览都是配置推算，不代表运行已经生效。

### Work Local 与 Codex Local

本项目同时面向 Windows 的 **Work Local 和 Codex Local**。本机双界面实测确认：在同一模型、同一目录且没有额外覆盖时，修改一次共享用户配置中的窗口值，两个模式的新聊天都会同步变化。

| 设置的原始窗口 | Work Local 实际可用窗口 | Codex Local 实际可用窗口 |
|---|---:|---:|
| 500K | 475K | 475K |
| 600K | 570K | 570K |

测试使用 `gpt-6-luna`、95% 有效比例、Codex 引擎 `0.163.0-alpha.11`。用户分别从两个界面新建聊天，依据真实运行记录核对；两轮之间未重启桌面应用。

设置按全部模型或指定模型组织，**不按 Work/Codex 模式分别保存窗口**。这两个本地模式使用共享设置是本项目的预期用法。不同项目配置、启动参数或请求覆写仍可能影响最终值；未验证旧聊天自动更新或全部客户端版本。复测步骤和详细边界见[验证范围](docs/VALIDATION.md#work-local-与-codex-local-双界面验证)。

当前实现按已核对客户端的规则处理窗口上限与压缩限制；配置不会突破服务端能力。模型目录、账户权限和客户端版本可能不同。刷新内置资料也不代表取得新模型权限。

发布前已完成 **33 项隔离测试、8 个正式真实模型回合，观察到 2 次自动压缩完成**；后续另完成 **4 个用户从 Work Local / Codex Local 界面发起的窗口对照回合**。压缩证据来自最初的引擎测试，双界面补测仅确认窗口同步，不扩大为两个界面的压缩参数均已验证。未测试所有模型或 60 万长输入极限。详见 [验证范围](docs/VALIDATION.md)。

## FAQ / 常见问题

### 如何修改 Codex Desktop 的上下文窗口或 Token 上限？ / How do I change the Codex Desktop context window or token limit?

安装 Windows 发布包后，让助手使用 `$context-window` 查询配置，再指定模型和窗口大小，例如“只把指定模型的上下文窗口设为 600k，其他参数不变”。支持全部模型或一个精确模型 ID。命令行示例见[直接使用命令](#直接使用命令)。

Install the Windows release, ask your agent to inspect settings with `$context-window`, then specify the model and raw token limit. For example: “Set only the selected model's context window to 600k; keep other settings unchanged.” See [usage examples](#usage-examples) for the executable commands.

### ChatGPT Work Local 和 Codex Local 的上下文设置通用吗？ / Do ChatGPT Work Local and Codex Local share context settings?

在已验证的 Windows 环境中，两者读取相同用户配置：同一模型、同一配置目录且没有额外覆盖时，修改后的新聊天使用相同窗口。500K 原始窗口对应 475K 有效窗口，600K 对应 570K（95% 有效比例）。不按两个模式分别存储窗口。详见[双界面验证](#work-local-与-codex-local)。

In the documented Windows environment, both modes use shared user settings when the model, configuration directory and overrides match. New chats showed 475K effective context for 500K raw and 570K for 600K raw at 95%. Separate per-mode window settings are not provided. See [desktop verification and scope](#desktop-verification-and-scope).

### 如何调整自动压缩触发阈值？ / How do I set the auto-compaction threshold?

指定 `--auto-compact-limit`，或直接说“把指定模型的自动压缩阈值设为 500k”。用 `default` 恢复默认；未指定的窗口和有效比例保持不变。阈值受模型目录和客户端规则限制，不能任意设大或据此关闭自动压缩。

Use `--auto-compact-limit` or ask the agent to set the automatic context compression threshold for the selected model. Use `default` to restore the default. The skill preserves unspecified parameters and checks the applicable limits; it does not provide an unlimited threshold or disable automatic compaction.

### 有效上下文比例与自动压缩阈值有什么区别？ / What is the effective context percentage versus the compaction threshold?

有效比例决定客户端预计可用窗口：例如 600K × 95% = 570K。自动压缩阈值决定何时尝试整理历史。二者可分别调整；“60万”始终表示 600000 个原始 token，不是承诺可用 60 万。

The effective percentage determines the expected usable window, such as 600K × 95% = 570K. The compaction threshold controls when the client attempts to compact history. They are separate controls; a raw token setting is not a guarantee of that many usable tokens.

### 需要安装 Python 或 PowerShell 7 吗？ / Can I use this skill without installing Python?

使用 `context-window-0.4.1-windows-x64.zip` 无需另装 Python、创建虚拟环境或安装 PowerShell 7。包内的 `bin/context_window.exe` 可直接由助手调用。GitHub 自动生成的 Source code 压缩包和 Git 源码不含 EXE；免环境安装请选择[Release 安装包](https://github.com/1dream1436/codex-context-window-skill/releases/latest)。

The Windows x64 release includes `bin/context_window.exe` and requires no separate Python installation, virtual environment or PowerShell 7. Choose the Windows ZIP from [Releases](https://github.com/1dream1436/codex-context-window-skill/releases/latest), not GitHub's automatically generated Source code archives. Python 3.11+ applies only when running or developing the source script.

### 修改后为什么旧聊天没有变化？能突破模型的服务端上限吗？ / Why is my existing chat unchanged, and does this unlock server-side capacity?

保存配置不代表旧聊天已应用；按需要新建聊天或重新加载，再从真实运行记录核对。这个项目只调整本机配置，不增加服务端容量或模型权限，也不调整普通 Chat 云端聊天。参见[生效与限制](#生效与限制)。

Saving settings does not prove an existing chat has applied them. Open a new chat or reload as appropriate and check actual runtime records. This local configuration skill does not increase server-side capacity, grant model access, or change regular cloud Chat. See [validation scope](docs/VALIDATION.md).

## 开发与贡献

以下Python 3.11+要求仅用于源码开发、测试与构建，普通用户使用Windows独立发布包无需安装Python。源码调用方式为 `python skills/context-window/scripts/context_window.py ...`。

```powershell
python -m unittest discover -s tests -v
python tools/release_check.py
python tools/build_release.py
```

自动测试只使用临时目录，不调用模型、不使用账户凭据、不修改真实配置。参见 [贡献说明](CONTRIBUTING.md)、[更新记录](CHANGELOG.md)、[安全报告](SECURITY.md)。

仓库结构：`skills/context-window/` 为可安装技能，`tests/` 为隔离回归测试，`tools/` 为发布检查及打包工具，`docs/` 为验证和维护说明。发布包不会包含真实配置、模型缓存、备份、登录资料或原始会话日志。

## 来源与许可

使用 [MIT License](LICENSE)。参数界面和内置刷新选项的设计参考 [smartcmd/codex-context-window](https://github.com/smartcmd/codex-context-window)；本项目保留自己的两种全局范围、事务记录与校验恢复实现。没有打包上游仓库源码。

配置语义参考 [官方配置说明](https://learn.chatgpt.com/docs/config-file/config-reference)、[官方模型元数据实现](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/openai_models.rs)；技能安装目录参考 [官方技能文档](https://learn.chatgpt.com/docs/build-skills)。外部文档会更新，兼容性以本项目验证记录为准。
