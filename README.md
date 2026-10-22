# xinman — Nuclear Signal Generator

第四届“新漫杯”智能仿核信号发生器：PC上位机、STM32F405固件、Gowin FPGA RTL、技术文档和原始测试记录。

## 当前交付范围

**单通道、单指数。实物测试主线：PC V0.10.3 + F405-N4.0.0 + FPGA 核信号单通道V4。**

链路：PC → CH340串口 → STM32F405 → SPI → Gowin FPGA → 8位DAC模块 → 示波器CH2。示波器CH2是测量输入，不代表发生器有第二输出通道。

保留的历史双通道/AD9767设计和旧版文档不代表本次实物交付能力。双指数和双通道明确不属于当前交付范围。

## 实测结果及限制

Hantek DSO2D15、BNC直连、DC、X1；示波器已自校准，没有独立有效校准参考。

| 精简核验 | 实测 |
|---|---|
| 3.3 V目标幅度 | 3.26 V，偏差−1.21% |
| 1 μs目标半高宽 | 1.028 μs |
| 100 μs目标半高宽 | 98 μs |
| 最长周期10 ms | 10.000 ms |
| 最短周期10 μs | 10.000 μs，即100 kHz |
| 高斯20%FS设置 | 去均值RMS 1.232 V；设备存在数字削顶 |

20%设置回读累计削顶点90,879，不能由累计值计算CSV窗口内削顶率。按暂定直流端点跨度折合19.56%FS，不构成无削顶高斯或绝对RMS准确度通过证明。

九点直流数据、三个独立插值点均保留；存在示波器跨量程零参考及DC读数差异，**绝对电压校准尚未定稿**。差分幅度可抵消固定零偏，不能消除增益、非线性和噪声偏差。

本仓库记录代表点和边界点工程核验，**不代表全参数范围、可溯源校准或完整赛题验收通过**。

[精简五组完整汇总](验收输出/2026-10-22_电压校准/精简五组/精简五组工程核验汇总.md)

## 导航

| 目录 | 内容 |
|---|---|
| [pc_app](pc_app/) | Python/PySide6源码、协议、单元测试、GUI测试、构建脚本、历次修复报告 |
| [stm32_firmware](stm32_firmware/) | C/ARM汇编、启动和链接文件、厂商驱动、主机测试及接线协议 |
| [FPGA_firmware](FPGA_firmware/) | Gowin工程、RTL、约束、testbench、构建和时序报告；含历史方案 |
| [firmware_artifacts](firmware_artifacts/) | 既有STM32各配置HEX/BIN/ELF/MAP |
| [docs](docs/) / [交付文档](交付文档/) | 技术方案、PDF/DOCX/PPTX；历史能力描述以本README及最新实测为准 |
| [验收输出](验收输出/) | 原始CSV、照片、分析与核验记录 |
| [releases](releases/) | 历史冻结包的小型固件、源码和报告 |
| [publication](publication/) | 编译复核、发布说明、清单及SHA256 |
| [AD9767模块资料V1.0_20260715](AD9767模块资料V1.0_20260715/) | 历史第三方参考材料，非本轮实测DAC配置 |

大EXE/历史ZIP位于[GitHub Releases](https://github.com/twinkle-air/xinman-nuclear-signal-generator/releases)，[资产清单](publication/release_assets.json)提供原路径映射。历史manifest仍描述原冻结目录，不能直接把拆分后的子目录当完整原包验manifest。

## PC运行与测试

Python 3.11+，在pc_app目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe launcher.py
```

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -m compileall -q launcher.py src tests
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:QT_QPA_PLATFORM
```

EXE构建另需PyInstaller，运行tools/build_release.ps1 -StageOnly。运行库适用各自许可证。

## STM32与FPGA构建

STM32需Arm GNU Toolchain、CMake、Ninja，运行stm32_firmware/tools/build_competition.ps1和test_competition.ps1。脚本中的工具路径需按本机调整。

当前FPGA工程为FPGA_firmware/基础方案/核信号单通道_V4；scripts/simulate.ps1用XSim仿真，scripts/build.ps1用Gowin EDA综合布局布线。XSim不是Gowin器件综合工具。scripts/common.ps1会为中文路径建立盘符映射。

匹配HEX/FS与接线须按对应文档确认；不要混用历史配置。N4台架构建启用开发安全旁路，A/B板在位及PG未接入实测。发布复核不自动烧录、不打开真实COM口。

## 已知问题与未覆盖项

- 20%FS高斯噪声存在数字削顶；跨量程绝对校准未定稿。
- 全码值/全宽度/全周期/噪声逐档、随机分布定量、更多能谱、所有参数组合和长期漂移未覆盖。
- measurement.analyze_scope对几乎相同间隔调用20箱直方图时可能出现NumPy范围异常；尚未修复，已发表测量记录使用独立离线算法复核。
- scope_csv_103_13.csv曾成功读取提取结果，但归档前F盘文件不可用；只有分析结果及当时SHA256，不能声称原始CSV已归档。
- 历史图纸/方案/报告含待验证设计，不等于实物能力。

## 许可

项目作者原创代码及原创文档采用[MIT License](LICENSE)。厂商驱动、CMSIS、第三方库、参考手册、比赛题目及模板保留各自权利和许可，不被MIT重新授权，见[第三方声明](THIRD_PARTY_NOTICES.md)。
