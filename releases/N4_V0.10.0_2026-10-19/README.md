# V0.10.0 / N4 配套程序

状态：**软件、主机测试、RTL仿真及工具编译通过；N4硬件尚未下载和复测。**保持原板卡、DAC、接线及模拟电路。

## 使用文件

| 文件 | 身份 | SHA256 |
|---|---|---|
| `programs/核信号工作台.exe` | PC V0.10.0 | `3EEB1F8CDA47110533CF0BC413F98397C6A37493DD078B7580764E7357464CC0` |
| `programs/nucsignal_f405.hex` | 外部F405-N4.0.0 | `E2FA6A310F208A02306DF6866DFCF044BC7D66729C3945AA3583871C2865660F` |
| `programs/g1_dac_spi.fs` | G1 FPGA-4.0.0 | `4B5CA1F5AC51F43B9F14E29A1D2BDEDD390E505A97D0B9B499ACD5AA9C479F6B` |

PC EXE也已更新到工作区根目录，散列与本包一致。PC仍支持旧B2/N3，但N4新功能只对N4固件开放。N4 HEX必须配V4 FS，不能配原V3 FS。

新增固定周期10–10000 μs、理论半高宽及τ扩展、高斯RMS控制、固定堆积许可；“实测与校准”入口提供校准、CSV分析、分布图、实测报告、配置保存和演示预设。

## 证据与源码

- `docs/单通道核信号_N4_升级与复测.md`：下载组合、操作顺序和测量限制。
- `docs/发布复核_V0.10.0.md`：实现范围及验证结果。
- `reports/`：PC构建/EXE独立smoke、UI检查、MCU主机测试/编译、FPGA仿真/时序报告。
- PC49项通过；MCU N4主机92项，旧N3/B2回归101/87项；FPGA SPI162、核信号18540、N4新增37091项。新增37000个DAC样点与整数参考逐点相符。
- FPGA50MHz建立/保持违例0/0，报告Fmax65.446MHz。它不是模拟输出带宽。
- UI截图中的N4能力标志为模拟设置，未连接串口，不是新版本实物运行证据。`N3_existing_scope_analysis.html`和参考CSV是旧N3实测数据的新分析，不是N4新实测。
- `sources/`保留源代码、测试、脚本及MCU vendor/startup/cmake；未包含Python虚拟环境和工具链。PC需Python3.11+、pyproject所列依赖与PyInstaller；MCU构建需Arm GNU14.2、CMake/Ninja；FPGA脚本使用Gowin1.9.10.02和Vivado2022.2进行布局布线/RTL仿真。
- 所有交付文件散列见`MANIFEST.sha256`，不包含清单本身。

## 边界及回退

新N4的模拟输出电压范围、50kHz波形质量、幅度±5%、高斯实测RMS/带宽、Co-60实测双峰和连续运行待复测。安全A/B/PG仍旁路；无第二物理通道。本次未增加可选实际双指数，也未将256项分位表扩展为1024项；低概率谱细节仍有量化限制。

已验收组合完整备份在相邻目录`accepted_V0.9.1_N3_before_N4_2026-10-19/`。回退请使用其中旧EXE、N3 HEX和V3 FS整套配对；旧归档及N3原产物未覆盖。
