# 许可和公开范围

本说明记录此次整理的版权许可依据，不是对全部专利、商标或其他第三方权利的法律保证。

## 可公开的源码

- 小米公开 Linux 内核树保留 `COPYING`，作为内核整体遵守 GPLv2。原有双许可证或其他兼容许可的文件保持原声明。
- 集成的是 KernelSU Next 固定标签的 **kernel 及其 UAPI**；随目录保留 GPLv2 `LICENSE`。没有把整个 KernelSU Next 项目中管理器/用户态的 GPLv3 许可套用到内核，也没有把那些代码混入仓库。
- LineageOS 音频基础源码保留原作者声明，固定来源提交并记录移植修改。
- 新的内核构建、检查和打包封装脚本按 GPL-2.0-only 提供；单独随附的 AOSP `mkbootimg.py` 为 Apache-2.0，保留其声明和 Apache 完整许可文本。

GPLv2 允许在满足条件时复制、修改和再分发。公开修改版应保留版权/许可证、说明修改，并提供编译产物对应的完整源码及构建脚本。源码仓库、构建附件中的提交记录和配置用于建立这种对应关系。

## 不进入公开仓库

MIUI 原厂 boot/ramdisk、原厂 12 个 `.ko`、固件二进制的用户副本、管理器 APK、SSH 凭据、手机日志和个人数据均未纳入。本仓库中的 ABI 参考只含符号名和数字 CRC，不含驱动程序。

Linux 的 GPL 不会自动赋予 MIUI ramdisk、应用和厂商二进制的再分发权。用户提供的原厂 boot 可以用于个人本地打包；若要公开分发含这些部分的 boot，需要单独核对相关许可。

仓库保留上游内核自带、具有各自声明的文件；不要删除其附带的版权或许可文件。工具链不在 Git 中再分发，构建时从 Bootlin 官方下载并校验。若未来把工具链本体一并发布，还需要处理其自身的许可证及对应源代码要求。

项目名称只是说明技术目标，不声称得到小米、LineageOS 或 KernelSU Next 的认可。此次代码审查不能证明不存在任何专利或其他权利争议。

## 依据

- [Linux kernel licensing rules](https://docs.kernel.org/process/license-rules.html)。
- [GPLv2 完整条款](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html)。
- [GNU GPL FAQ](https://www.gnu.org/licenses/gpl-faq.html)。
- 仓库中的 `COPYING`、`kernel/kernelsu/LICENSE` 和每个文件的原有许可声明。
