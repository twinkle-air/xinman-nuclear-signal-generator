# 基础方案：FPGA-G1 + ATK-MO8008 第一阶段

2026-10-11新增独立[通信联调版](通信联调/README.md)：H5 DAC接线保持，H6新增STM32 SPI控制。当前目录的按键工程继续保留，下载通信版时请选择其独立`g1_dac_spi.fs`。

本目录为本工程单通道 8 位基础方案，与同级“进阶方案”分开保存。配置日期：2026-10-03。

本版已由用户的 Programmer 截图确认 SRAM Program 执行至 Finished；2026-10-11 的示波器照片确认斜坡周期 256 μs、脉冲周期 1 ms，用户报告模式验证无问题。详见 [基础方案实测记录](reports/基础方案实测记录_2026-10-11.md)。

## 工程与实物版本

- Gowin FPGA Designer V1.9.10.02；GW2A-LV18PG256C8/I7，版本 C。
- 板载 50 MHz 时钟 T7；不使用 PLL、DDR3、板上 GD32 或外部 STM32 通信。
- 正点原子 ATK-MO8008 V3.3，整排 40 针母座直插 G1 的 H5，依据用户 IMG_8672.JPG 及本地板级原理图。
- 本工程是单路 8 位 DAC 联调程序。整排连接方向与无错位仍应由断电通断测量确认。

## 直接打开

在本目录打开 PowerShell，执行：

```powershell
.\scripts\open_project.ps1
```

脚本为本方案目录建立英文盘符别名，并打印工程路径；在 Gowin 使用 File → Open 打开打印出的 `g1_dac_stage1.gprj`。所有文件仍在原目录，未复制到其他盘。工程器件、RTL、CST、SDC 已配置。脚本不会自动点击 Gowin 窗口。

若要自己打开，在 Gowin 选择 File → Open，打开盘符别名下的 `g1_dac_stage1.gprj`。建议后续也从英文别名路径操作；盘符由脚本选择，基础版与进阶版可能不同。重启后重新运行脚本可重建别名。

## 功能与操作

| 状态 | 数字输出 | 预期示波器现象 |
| --- | --- | --- |
| 上电／复位 | 固定码 128 | 恒定电平，绝对电压需实测 |
| 按 key[0] 一次 | 0→255 循环斜坡 | 约 3.90625 kHz 锯齿波 |
| 再按 key[0] | 指数衰减脉冲 | 每 1 ms 一个脉冲，重复率 1 kHz |
| 再按 key[0] | 回到固定码 128 | 恒定电平 |
| 按 key[1] | 复位并回到固定码 | 松开后继续固定码测试 |

这里的 key[0] 是板级官方约束的 D11，key[1] 是 F10，均低电平有效。key[0] 消抖 10 ms，长按只切换一次。key[1] 为同步后的复位，不需要精确消抖计数。

DAC 时钟 1 MHz，占空比 50%。所有内部寄存器仍由 50 MHz 时钟驱动。数据在 DAC 时钟下降沿更新，500 ns 后出现上升沿；目前按上升沿采样制定联调假设。实际 DAC 芯片型号和采样沿须依据对应器件资料确认。

脉冲码表：前 64 个样本采用 `16 + round(224 * exp(-n/12))`，随后回到基线 16；每 1000 个样本重复。采样间隔 1 μs，时间常数 12 μs；这用于联调，不代表已实现可参数化的完整核脉冲模型。DA_OUT 电位器会影响模拟输出，码值不能直接当成伏特数。

## 当前连接表

| 信号 | H5 针号 | FPGA 球位 |
| --- | --- | --- |
| DAC D0 | 17 | B14 |
| DAC D1 | 18 | A15 |
| DAC D2 | 19 | A12 |
| DAC D3 | 20 | B11 |
| DAC D4 | 21 | B12 |
| DAC D5 | 22 | C12 |
| DAC D6 | 23 | C11 |
| DAC D7 | 24 | A11 |
| DAC CLK | 25 | C9 |
| 模块 5 V | 40 | 板载 +5V_IN |
| 模块 GND | 37、39 | GND |

DAC 的 9 个输出均在 Bank 7，LVCMOS33、驱动 4 mA。H5-38 为板载 3.3 V，对应模块 `/` 位。

ADC CLK、OTR、D0～D7 没有加入输出逻辑。Gowin `unused_pin=default` 使未用 GPIO 为输入三态弱上拉；编译报告已复核 H5-27～36 的球位都是 `in`。ADC CLK 不是有效采样时钟。此设置避免输出争用，不构成对 ADC 输出电平与 FPGA Bank 兼容性的验证。

USB／HDMI／扩展口共用同一个 5 V 网络。直插由该网络给 DAC 供电，不能再并接一个独立 5 V 电源。

## 重编译与仿真

```powershell
.\scripts\build.ps1
.\scripts\simulate.ps1
```

- `build.ps1`：使用本机 Gowin，综合、布局布线、生成码流，保留 `reports/build.log`，并检查码流确实重新生成。
- `simulate.ps1`：使用本机 Vivado 2022.2 自带 XSim，仅执行通用 RTL 仿真；高云芯片综合与码流生成仍使用 Gowin。保留 `reports/simulation.log`，结束后删除 `.sim_work` 临时文件。
- 工具安装路径可通过脚本的 `GowinBin`／`VivadoBin` 参数覆盖。
- 在 Gowin Console 也可执行 `source R:/scripts/build.tcl`，按实际别名替换 R:。Tcl 脚本显式设置顶层、报告选项、未使用引脚策略以及保留 JTAG。

## 本次已验证

1. Gowin 综合、布局布线和码流生成完成；输出 `impl/pnr/g1_dac_stage1.fs`。
2. 50 MHz 内部 setup/hold 违例均为 0；最差 setup slack 13.541 ns，最差 hold slack 0.322 ns。报告的内部 Fmax 154.820 MHz 不代表 DAC 可以运行到该频率。
3. 183 个逻辑资源、88 个寄存器，均小于器件资源的 1%；12 个 I/O，9 个 DAC 输出。
4. 生成的 Pin/Ports 报告与当前直插引脚表一致；ADC 所接脚没有输出驱动。
5. RTL 仿真通过 2309 个 DAC 样本，检查固定码、300 点斜坡与回绕、两个完整脉冲周期、时钟周期、至少 500 ns 数据稳定时间、模式返回、上电复位、按键短抖动、长按与模式循环。

SDC 约束了 50 MHz 内部时钟，并将异步按键输入至同步器的路径排除。**尚未为 DAC 外部接口建立器件级 setup/hold 签核**，当前代码的 500 ns 间隔只在 RTL 层得到验证。本版已有 SRAM Program 完成及模拟输出的用户截图；斜坡与脉冲的周期、幅度比例符合联调预期，实测为下降斜坡及负向脉冲。脉冲细节、时间常数、幅度校准与负载条件仍需进一步测量；未执行 Flash 固化。

命令行编译曾提示不能写入用户 AppData 的 `sh.log`；工程内综合、布局布线报告和码流均正常生成，此提示不表示编译失败。

## 上板联调

1. 断电确认模块 5 V→H5-40、GND→H5-37/39，没有错位或 5 V/GND 直接短路，并核对模块芯片与 ADC 输出电平兼容性。
2. 首次通过 Programmer 选择对应器件，使用 SRAM Download，加载 `impl/pnr/g1_dac_stage1.fs`；先不固化 Flash。
3. 示波器接 DA_OUT，先检查固定码，再用按键检查斜坡和脉冲；同时测 DAC CLK 和数据。模拟幅度、负载、毛刺和供电余量由实测确认。
4. 波形稳定后再接入 STM32 SPI 寄存器协议。可复用 `dac_test_core` 的 `requested_mode` 接口，并将码表、周期、幅度改为参数或寄存器；保留现有 `../../stm32_firmware/docs/fpga_spi_register_map.md` 协议边界。

## 文件布局

- `rtl/`：可综合顶层与 DAC 测试核心。
- `constraints/`：当前直插 CST、内部时钟 SDC。
- `tb/`：可复现的行为测试。
- `scripts/`：打开、编译、仿真脚本。
- `impl/`：本次 Gowin 生成的码流、网表和实际报告。
- `reports/`：编译与仿真日志。

器件／板级来源见 `../../docs/hardware/FPGA-G1_开发参考.md`，第一阶段边界见 `../../docs/software/软件实现方案.md`。
