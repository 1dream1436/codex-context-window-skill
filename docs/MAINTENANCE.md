# 维护与发布

## 模型资料更新

资料有变化时无需立刻修改脚本。先执行 `status`，核对模型 ID 和上限，再使用 `refresh` 预览差异。默认从本机缓存读取；`--refresh-from-bundled` 只读取当前已安装 Codex 的内置资料，并非联网获取最新模型。

确认来源适用后加 `--apply`。刷新采用新字段，再叠加有记录的选择；模型消失、目录被外部编辑或新上限使压缩选择不适用时停止。不要删除冲突检查来强行刷新。

## 客户端变化

当 Codex 更新配置键、目录结构、窗口或压缩计算规则时，核对官方实现，修改相关逻辑和隔离测试，再按授权范围做真实复测。更新验证范围中的客户端版本和证据。不要只根据模型名称推断兼容性。

## 发布流程

1. 更新 `scripts/context_window.py` 中的版本、技能元数据、CHANGELOG 和验证说明。
2. 在干净工作目录运行隔离测试与 `tools/release_check.py`。
3. 执行 `tools/build_release.py`，检查 ZIP 仅包含技能文件及许可证。
4. 提交英文说明，推送后确认 GitHub CI 通过。
5. 在通过检查的提交上建立 `vX.Y.Z` 标签，创建 GitHub Release，上传 ZIP 和 SHA-256 校验文件，发布说明列出验证边界。

本仓库不自动调用模型。发布GitHub Release后，`release.yml` 在Windows运行隔离测试和发布检查，使用固定版本PyInstaller打包独立EXE，清空PATH后验证查询、预览、写入及恢复，再上传Windows x64技能ZIP和SHA-256校验文件。普通推送不会发布新版本。

开发者仍使用Python 3.11+；它不再是Windows发布包用户的安装前提。EXE只在Windows runner生成，不提交进Git。若构建失败，修复后通过workflow_dispatch传入既有tag重试；工作流只在全部检查通过后上传，不覆盖已存在的资产。
