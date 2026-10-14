# MIX 2S KernelSU Next

小米 MIX 2S（`polaris`）的 Linux 4.9 KSU 内核源码，针对 **MIUI V12.5.1.0.QDGCNXM / Android 10** 整理。本项目是社区移植，不代表小米、LineageOS 或 KernelSU Next 官方。

固定 KernelSU Next `v3.4.0-legacy`（33294）和 Bootlin GCC 8.4.0，只构建带 KSU 的版本。源码已经包含音频修复、手动 Hook、授权读写及旧内核密钥环兼容修复。

## 实机验证范围

测试设备可以启动；Shell Root、跨启动授权恢复、管理器识别、Zygisk Next 的 32/64 位注入和 LSPosed 框架 Hook 已确认工作。原厂 12 个驱动保持原样。此前用户测试过扬声器、录音和相机录像；这不代表所有硬件、长期耗电和所有第三方模块都已全面验证。

完整出处、修改说明和测试边界见 [来源记录](build-support/provenance.json)、[修改说明](build-support/CHANGES.md) 和 [许可证说明](build-support/LICENSING.md)。

## GitHub 构建

默认使用私有仓库。将源码推送到 `main`，在同仓库的私有 `stock-input` Release 保存原版 boot 后，在 **Actions → Build polaris KernelSU Next boot.img → Run workflow** 手动构建。首次设置见 [GITHUB-SETUP.md](build-support/GITHUB-SETUP.md)。

构建固定使用 Ubuntu 22.04、两个编译任务和带 SHA256 校验的工具链。Action 本身固定到具体提交，不执行远程 KSU 安装脚本，不自动升级 KSU。工作流只有读取仓库权限，不会创建 Release 或自动刷机。

成功后下载 `polaris-boot-提交号` 产物 ZIP，解压即可得到可刷入的 **`boot.img`**、打包报告和校验清单。另一份附件包括：

- `Image.gz-dtb`：KSU ARM64 内核及设备树；**不是可直接刷入的 boot.img**。
- `kernel.config`、`Module.symvers`、`SHA256SUMS`。
- `validation.json`、`build-manifest.json`、来源记录和构建日志。

验证失败不会上传成功产物。云端首次运行仍需在 GitHub 实际确认，离线构建验证不能代替云端运行记录。

## Linux / WSL 本地构建

需要 Linux 文件系统中的工作目录。内核包含大小写同名文件，不应在普通 Windows NTFS 目录展开后构建；WSL 请放在 Linux 家目录，不要放在 `/mnt/c`、`/mnt/f`。

```bash
sudo apt-get update
sudo apt-get install -y build-essential bc bison flex libssl-dev libelf-dev python3 curl bzip2 xz-utils
bash build-support/run-tests.sh
bash build-support/build.sh
```

首次运行会下载并校验固定工具链。也可指定已安装工具链：

```bash
TC_PREFIX=/absolute/path/aarch64--glibc--stable-2020.02-1/bin/aarch64-linux- JOBS=2 bash build-support/build.sh
```

默认输出目录为 `out/` 和 `dist/`，均不进入 Git。`OUT_DIR`、`DIST_DIR` 可改为其他目录。脚本总是使用已验证配置，不提供非 KSU 模式。直接指定 GCC，构建无需使用上游 Python 2 的编译器包装脚本。

## 本地打包 boot.img

本仓库不含 MIUI 原厂 boot、ramdisk、驱动二进制或手机日志。使用你自行备份的原版 boot，在本地打包：

```bash
python3 build-support/repack-boot.py --stock /private/path/boot.img --kernel dist/Image.gz-dtb --output dist/polaris-ksunext-boot.img
```

打包器限定已验证的原厂 boot SHA256，保持原厂 ramdisk、启动参数和布局；更新内核及校验，移除失效的原厂 BootSignature。需要已经解锁的 bootloader。本项目不为其他 ROM 或其他 boot 格式提供兼容保证。

含原厂 ramdisk 的 boot 不提交到源码 Git 历史；本方案只在私有 Release 保存原版素材，并在私有 Actions 产物中输出新 boot。公开发布需另行确认 ramdisk 的再分发许可。不要把 SSH 私钥、ADB 报告、个人数据或原厂 `.ko` 加入仓库。

## 更新 KSU

这是固定版本，不是跟随最新分支的自动更新项目。更换 KSU 时，应在独立分支调整源码和 `provenance.json`，审查 `build-support/CHANGES.md` 中列出的兼容修复，再跑主机测试、ABI 检查和实机测试。不能只替换版本号或仅凭编译通过发布。

## 许可证和来源

内核作为整体依照 [COPYING](COPYING) 中的 GPLv2 分发，保留各文件原有版权和兼容许可证。此次集成的 KSU 内核目录自带 GPLv2 `LICENSE`；未包含管理器/ksud 用户态代码。AOSP 打包工具按 Apache-2.0 提供。原厂驱动和 boot 的许可不能由内核 GPL 自动推定。

本仓库是修改后的版本，不是原厂内核的逐字节复现。发布编译产物时，请同时提供该构建对应提交的完整源码、配置和构建脚本；原作者版权声明保持原样。
