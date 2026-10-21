# Contributing

欢迎用简体中文或英文提交 Issue 和 Pull Request。

1. 先阅读 README 和验证范围，描述实际问题、客户端版本与期望结果。
2. Fork 后建立独立分支，在临时配置目录复现问题。
3. 修改应保持未指定参数和无关配置，涉及配置写入时补充有意义的隔离回归测试。
4. 提交前运行 `python -m unittest discover -s tests -v` 和 `python tools/release_check.py`。
5. 提交说明、分支名及标签推荐使用英文；解释和讨论可用中文。

Python 3.11+，运行及测试无需第三方包。CI 不进行真实模型调用。不要将真实登录资料、模型缓存、备份或完整会话日志放进提交或 Issue。

兼容性变更请同步更新 `docs/VALIDATION.md`。未做真实运行验证时，明确标注为配置推算或隔离测试，不能声称所有客户端都已生效。
