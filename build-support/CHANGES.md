# 移植修改与维护记录

整理日期：2026-10-14。修改基线：已实机验证的 `audiofix3 + bootfix2`。原作者版权声明和许可证保留；修改文件加入日期说明。本地首次 Git 提交是自动生成的源码快照，提交署名不表示这些上游代码由快照整理者创作。

## 内核和模块 ABI

- 小米 `dipper-q-oss`，提交 `dcfb1676925aec83b06ae04fd8ca989ced75067c`。
- 根据原厂 exfat 的 DWARF 恢复 `ravg.proc_load`、`task_struct.top_app` 和 `task_struct.woken_by_top_app` 的真实类型和位置。
- 保持 MODVERSIONS；没有修改原厂驱动或伪造 CRC。
- 受控编译比较过 GCC 4.9 与 8.4：184 个单元、3283 个导出 CRC 无差异。最终 1381 个模块版本引用全部匹配。

## 音频

公开基础实现取自 LineageOS `adbb39e2b28e776556323d8530a396cc27db8edb` 的 `techpack/audio`；保留该项目的原作者声明。

补齐 DSP/APR/SoundWire/regmap 等内核基础服务，启用 `SND_SOC_MSM_STUB`、`SND_SOC_MSM_HDMI_CODEC_RX`、`SND_SOC_TAS2559`。原厂声卡、codec 等外置驱动继续使用系统中的原文件，避免导出冲突。公开代码不等同于原厂全部音频实现的二进制复现。

## KSU

固定官方 `v3.4.0-legacy` 提交 `8af3d4fec33be32fa5d3f8dae4f380fac45bf2cd`，保留官方内核及 UAPI 的许可证。

- 手动接入 execve/execveat、访问检查、stat/fstat、init.rc 读取、reboot 通道、输入安全模式等路径；KPROBES 关闭。
- 4.9 文件读写签名和位置更新；旧内核字符串、分配及溢出检查适配。
- 不向公共 seccomp 结构添加字段，使用旧内核 `put_seccomp_filter`。
- 固定版本 33294，避免无独立 KSU Git 历史时报告 fallback 1。
- init.rc 代理停用条件；只允许 init→ksu、`/data/adb/ksud`、无 NNP 的 nosuid 例外，随后仍执行其他 SELinux 检查。
- 授权读写的短 I/O、errno、凭据恢复、格式长度检查和保存 fsync。
- 对旧内核加密文件打开，临时使用 init session keyring；捕获引用，结束后恢复及释放临时凭据。普通和 nonotify 打开统一接入。没有在 override 期间执行 commit_creds。
- 管理器 APK 错误日志包含真实 errno。

兼容思路参考：

- [旧内核 nosuid 问题](https://github.com/tiann/KernelSU/discussions/955)。
- [KernelSU v0.9.5 的密钥环兼容](https://github.com/tiann/KernelSU/blob/v0.9.5/kernel/kernel_compat.c)；本项目采用临时凭据，未照搬永久提交凭据方式。

## 本次仓库整理

源码逻辑保持测试基线。新增固定配置、构建/验证/打包脚本、来源和许可说明、GitHub Actions。先生成 SELinux 头文件，再进行整体并行构建，避免干净构建时的生成依赖竞争。

修复 KSU `include/uapi` 的原有悬空链接，并将上游文件链接物化为等价文件；列表见 `provenance.json`。这便于源码归档，Windows 的大小写冲突仍须用完整 Git 对象仓库/归档保存，并在 Linux 文件系统构建。

## 验证边界

68 项主机故障注入断言只覆盖兼容函数逻辑，不模拟真实手机 fscrypt、init 或 SELinux。公开构建验证检查固定配置、整个已测试导出 CRC 集合、KSU 链接、ARM64 gzip 及 54 个 DTB。

实机已确认 Root、两次启动授权加载、管理器识别、Zygisk 32/64 位及 LSPosed Hook。第三方 iMPad 插件的 QQ PadUtil Hook 有兼容报错；不属于本项目已保证可用的功能。长时间待机、耗电、全部硬件及其他 ROM 尚未全面验证。

更新构建配置、结构定义、导出接口或工具链后，必须重新审查原厂模块兼容；不能自动重写 ABI 参考以掩盖失配。
