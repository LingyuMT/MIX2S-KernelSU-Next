# 首次 GitHub 设置

1. 使用公开源码仓库的 `main` 分支，不上传原厂 boot、ramdisk、原厂驱动、管理器 APK 或个人日志。
2. 打开 **Actions → Build polaris KernelSU Next kernel → Run workflow**，选择 `main`。
3. 构建成功后，下载 **polaris-ksunext-提交号** 附件 ZIP。附件包含 `Image.gz-dtb`、配置、符号表、校验清单、来源、许可证和验证报告；它不是完整 boot.img，不能直接刷入 boot 分区。
4. 按 README 的本地打包步骤，将内核与自己保存的、匹配目标系统的原版 boot 合成镜像。原版 boot 的 SHA256 必须为 `729d574ce3c67ce7516b2a65a1d7aaf7acc3a5e69a0f0cbfcee7098216689de2`。

不需要仓库 Secrets、个人令牌或服务器 SSH 密钥。工作流只授予 `contents: read`，不获取原厂素材，不创建 Release，不自动刷机，也不更新 KSU。

工作流默认只手动触发；首次云端运行应核对结果，本地验证不能代替 GitHub Actions 运行记录。下载内核时使用附件中的构建提交号查找对应源码。
