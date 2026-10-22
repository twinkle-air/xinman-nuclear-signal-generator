# 立创逻辑派 FPGA-G1 开发参考

核对日期：2026-09-25。用途：本工程 FPGA-G1 与 ATK-MO8008 V3.3 模块的后续开发索引。资料中的引脚、供电和时序结论以实物丝印、对应板版原理图和编译报告的最终核对为准。

## 官方资料入口

| 内容 | 入口 | 本工程用途 |
| --- | --- | --- |
| 文档总目录 | [FPGA-G1 文档中心](https://wiki.lckfb.com/zh-hans/fpga-ljpi/) | 按章节查软件、语法、板载接口和示例 |
| 资料包 | [资料下载中心](https://wiki.lckfb.com/zh-hans/fpga-ljpi/open-source-hardware/download.html) | 原理图、例程、工具及其他原始资料 |
| 开源硬件、引脚表 | [开源硬件与 Layout](https://wiki.lckfb.com/zh-hans/fpga-ljpi/open-source-hardware/) | 板级工程、引脚分配表和 `.cst` |
| 硬件接口 | [接口说明](https://wiki.lckfb.com/zh-hans/fpga-ljpi/open-source-hardware/port.html) | 供电、扩展排针、下载、Flash、DDR3 |
| Gowin 安装 | [Gowin](https://wiki.lckfb.com/zh-hans/fpga-ljpi/beginner/gowin-soft.html) | FPGA 综合、布局布线和烧录 |
| Gowin 工程 | [Gowin 环境验证](https://wiki.lckfb.com/zh-hans/fpga-ljpi/beginner/gowin-soft-text.html)及[LED 工程示例](https://wiki.lckfb.com/zh-hans/fpga-ljpi/beginner/led.html) | 创建工程、约束、编译和时序报告 |
| 仿真 | [ModelSim 安装](https://wiki.lckfb.com/zh-hans/fpga-ljpi/beginner/modelsim.html)、[库配置](https://wiki.lckfb.com/zh-hans/fpga-ljpi/beginner/modelsim-text.html) | RTL 仿真及 Gowin 原语库 |
| IP 和进阶 | [PLL](https://wiki.lckfb.com/zh-hans/fpga-ljpi/beginner/ip-pll.html)、[ROM](https://wiki.lckfb.com/zh-hans/fpga-ljpi/beginner/ip-rom.html)、[RAM](https://wiki.lckfb.com/zh-hans/fpga-ljpi/beginner/one-ram.html)、[FIFO](https://wiki.lckfb.com/zh-hans/fpga-ljpi/beginner/fifo.html)、[DDR3](https://wiki.lckfb.com/zh-hans/fpga-ljpi/beginner/ddr3.html) | 波形表、缓存和以后扩展 |
| 板上通信 | [I/O 交互](https://wiki.lckfb.com/zh-hans/fpga-ljpi/communication/io.html) | GD32 与 FPGA 之间的基础通信例子 |
| 排错 | [常见问题](https://wiki.lckfb.com/zh-hans/fpga-ljpi/question/problem.html) | License、SSPI 管脚复用、烧录和测试 |

本地资料在 `C:\Users\Twinkle\Desktop\FPGA`：`04配套程序\立创逻辑派FPGA_G1_IO.cst`、`04配套程序\逻辑派引脚分配表.pdf`、`06逻辑派硬件素材` 中的开源板级原理图，以及 `01官方资料\FPGA` 中的 GW2A 器件手册。该目录作为只读原始资料使用。

## 已核对的板级事实

- 主 FPGA 为高云 GW2A-LV18，Gowin 新建工程选择 GW2A 系列、GW2A-18、PBGA256、C8/I7、器件版本 C；最终 Part Number 按板上芯片丝印确认。板上另有 GD32F303 MCU，不能把该板当成只有 FPGA 的单芯片板。
- 板载系统时钟为 **50 MHz**，本地官方 `.cst` 指定 `sys_clk` 位于 **T7**，`LVCMOS33`。时钟周期为 20 ns；第一阶段应建立 20 ns 时钟约束，查看布局布线后的时序分析报告。
- 官方接口说明记载 W25Q64 **64 Mbit / 8 MB** QSPI Flash，可用于 FPGA 配置固化；另有 MT41J128M16JT-125-K **2 Gbit / 256 MB** DDR3，连接 FPGA Bank 4/5/6，相关 Bank 电压为 1.5 V。第一阶段固定波形无需 DDR3。
- 板上还提供 micro HDMI、USB 1.1、TF 卡、TFT 接口、RGB LED、按键、数码管；文档总目录有对应的板载案例。扩展排针共引出官方所述 **65 个 FPGA I/O** 和 **6 个 MCU I/O**，但需按 H5/H6 原理图逐个选择，不能把所有排针都视作 FPGA I/O。
- 板载下载器支持 FPGA 下载、Flash 固化和在线调试，并兼有串口。官方说明 FPGA 与 ARM 的下载模式需切换，不能同时使用同一个下载接口。
- 官方接口说明指出下载器、USB、HDMI 供电和扩展排针的 5 V 属于同一电源网络，排针接入外部电源只能是 **5 V**。不要将不同的 5 V 电源直接并接到该网络。DAC 模块如使用独立 5 V 电源，必须与 FPGA 共地，但其 5 V 线不接到 FPGA 的 5 V 排针。DAC 模块的供电电流和数字输入阈值仍需以该模块的对应资料或实测确认。

## 当前实物：40 针直接插接

用户照片 `C:\Users\Twinkle\Downloads\IMG_8672.JPG` 显示 ATK-MO8008 的整排母座直接插在 G1 的 H5 上，模块的 5 V／GND 端位于 G1 的 micro HDMI／USB 端。根据照片中模块丝印、官方功能框图与本地 H5 原理图，下面是**假定整排无错位、两列连接方向正确时**的对应关系；照片不能代替断电通断测量。

| 模块 DAC 信号 | H5 | FPGA 球位 |
| --- | --- | --- |
| D0 | 17 | B14 |
| D1 | 18 | A15 |
| D2 | 19 | A12 |
| D3 | 20 | B11 |
| D4 | 21 | B12 |
| D5 | 22 | C12 |
| D6 | 23 | C11 |
| D7 | 24 | A11 |
| DAC CLK | 25 | C9 |
| 5 V | 40 | +5V_IN |
| GND | 37、39 | GND |

H5-38 是 +3.3 V，对应模块标 `/` 的位置，不能当作 DAC 的 5 V 输入。上述 DAC 数据与时钟球位属于 Bank 7；官方板上按键与本地约束文件也表明 Bank 7 使用 3.3 V。上电前应断开 USB，测量模块 5 V 与 H5-40、模块 GND 与 H5-37/39 的通断，并检查 5 V 与 GND 没有直接短路。直插确认成立后，DAC 可从 G1 的同一 5 V 网络供电，无须再把独立 5 V 接到模块；实际供电余量和负载仍需测量。

整排直插同时连上了模块 ADC 接口：ADC CLK 对应 H5-27，OTR 与数据输出对应 H5-28～36。阶段一只使用 DAC；这些 ADC 输出所接 FPGA 脚必须保持输入，不能加载将整排 GPIO 全部设成输出的测试程序。ADC 接口电平兼容性还需依据模块准确器件资料核对。

## 之前拟定的逐线接线方案

以下映射来自本地 G1 开源原理图的 H5 网络标号，属于电气网络映射。**H5 实物 1 脚方位尚未根据实物丝印核实，接线时先确定 1 脚和奇偶排方向。**

此表只用于单独跳线连接，**不适用于上面的整排直接插接**；后续代码应按实际连接方式选择约束。

| H5 排针号 | FPGA 球位 | 第一阶段拟用信号 |
| --- | --- | --- |
| 1 | K16 | DAC D0 |
| 2 | J15 | DAC D1 |
| 3 | J14 | DAC D2 |
| 4 | J16 | DAC D3 |
| 5 | F14 | DAC D4 |
| 6 | F16 | DAC D5 |
| 7 | J13 | DAC D6 |
| 8 | H11 | DAC D7 |
| 9 | E16 | DAC CLK |
| 37 | GND | DAC GND |

ATK-MO8008 V3.3 有两组重复的 D0–D7。第一阶段只连接**与 DA_OUT 对应、同组有 `CLK` 的 DAC 数字接口**；另一组 `CLK/OTR` 是 ADC 侧。板上 FPGA 的数字输出拟设为 `LVCMOS33`。在插线前核对 DAC 模块的数字输入高电平门限，不能仅凭模块 5 V 供电推断其输入电平。`DA_OUT` 是模拟输出，应接示波器，不接 FPGA 数字脚。

## 建议开发顺序

1. 用官方 LED 示例验证 Gowin 工程创建、器件型号、T7 时钟、下载器和板上配置流程。编译后查看 Pin/Ports 与 Timing 报告。
2. 新建本项目工程，先做固定码和低速斜坡输出，确认 H5 D0–D7 与 CLK 的逻辑关系、模块供电和 DA_OUT 波形。
3. 再做查表单脉冲；需要节省逻辑资源时参考官方 ROM/RAM 示例。输出时钟与数据时序必须根据 DAC 模块的确切器件手册和实测波形确定。
4. 最后增加可配置脉冲参数、随机事件、噪声以及 MCU 通信。FPGA-G1 自带 GD32 与本工程外部 STM32F405 是两套不同 MCU，官方板载 I/O 交互示例可借鉴，但不能直接当成本工程的 STM32-FPGA 协议实现。

## 尚待实物验证

- 当前开发板的 PCB/芯片版本与开源 V1.0 原理图是否一致；H5 的 1 脚定位。
- H5 所选 I/O 的 Bank 供电和真实空闲状态；完整约束需以目标 Gowin 编译报告复核。
- ATK-MO8008 V3.3 的 DAC 芯片准确型号、数字输入阈值、时钟采样沿、最大频率、输出幅度和负载要求。
- 单独供电 DAC 时的上电顺序；避免 FPGA I/O 在 DAC 未上电时经输入保护结构反向供电。
