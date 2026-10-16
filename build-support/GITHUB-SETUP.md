# GitHub 构建和 Release

1. 使用公开源码仓库的 `main` 分支，不上传原厂 boot、ramdisk、原厂驱动、管理器 APK 或个人日志。
2. 打开 **Actions → Build polaris KernelSU Next kernel → Run workflow**，选择 `main`。
3. 构建和校验成功后，独立的 **Publish polaris kernel release** 工作流自动发布 Release。失败的构建不会触发发布。
4. 在仓库 **Releases** 下载 `polaris-ksunext-提交号.zip`，内含 `Image.gz-dtb`、配置、符号表、校验清单、来源、许可证和验证报告。也提供单独的内核及校验文件下载。这些文件不是完整 boot.img，不能直接刷入 boot 分区。
5. 按 README 的本地打包步骤，将内核与自己保存的、匹配目标系统的原版 boot 合成镜像。原版 boot 的 SHA256 必须为 `729d574ce3c67ce7516b2a65a1d7aaf7acc3a5e69a0f0cbfcee7098216689de2`。

无需配置 Secrets、个人令牌或服务器 SSH 密钥。内核构建仅有 `contents: read` 权限；发布任务单独申请 `actions: read` 和 `contents: write`。发布前再次核对成功构建、main 分支、来源仓库、提交号、校验结果和附件文件清单。先创建草稿，上传完整后再公开；标签指向实际构建的源码提交。

Actions 附件保留 14 天，Release 附件用于长期下载。也可在 **Publish polaris kernel release → Run workflow** 填入之前成功构建的 Run ID 补发；原 Actions 附件必须仍可下载。同一次构建重复发布会跳过已公开的 Release。

两条工作流均不获取原厂素材，不发布完整 boot.img，不自动刷机，也不更新 KSU。
