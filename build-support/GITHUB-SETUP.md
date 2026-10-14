# 首次 GitHub 设置

本地已经准备好源码仓库；本文件中的操作在用户确认上传之后执行。

1. 创建 **Private** 仓库，将准备好的 `main` 分支推送过去。源码仓库没有原厂 boot 或 SSH/手机日志。
2. 在同一个私有仓库创建 tag 为 `stock-input` 的 Release，上传本地 `private-input/polaris-stock-boot.img` 为素材。不要将其放入源码 Git 历史。原文件 SHA256 必须为 `729d574ce3c67ce7516b2a65a1d7aaf7acc3a5e69a0f0cbfcee7098216689de2`。
3. 打开 **Actions → Build polaris KernelSU Next boot.img → Run workflow**，选择 `main`。
4. 构建成功后，下载 **polaris-boot-提交号** 产物 ZIP，解压得到可以刷入的 `boot.img`、打包报告和 SHA256 校验清单。另一份产物保存内核、配置和构建证据。

流程只用 GitHub 提供的临时 `GITHUB_TOKEN` 和 `contents: read` 权限读取同仓库私有 Release；无需个人访问令牌、SSH 密钥或外部下载服务。缺失素材、素材哈希错误或仓库不是 Private 时会在编译前停止。它不会自动创建公开 Release、自动刷机或更新 KSU。

默认只手动触发，首次推送时不会因素材还没上传就启动长时间编译。GitHub 第一次真实运行仍需核对结果；本地验证不等于已在 GitHub 执行成功。

如果未来想公开源码，可以另建不带 MIUI 素材和 boot 产物的源码仓库。将此仓库改为 Public 会涉及已有的私有素材/产物；需先审查相应再分发许可与公开范围。
