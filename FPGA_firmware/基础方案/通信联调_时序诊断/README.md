# DAC 时序诊断版（2026-10-12）

更新：2026-10-18。本目录版本已完成本轮单通道板级检查：此前起始深尖峰及恢复段额外下跳在后续多档观察中未再见。支持接口时序方向的排查结论，器件级根因仍未独立确定。原通信联调目录和STM32固件保留。

硬件结果、量测表及剩余验证项见[板级验收记录](../../../stm32_firmware/docs/基础方案板级验收记录.md)。当前工作程序User Code为0x0000743C；Flash固化已验证External Flash Mode → `exFlash Erase,Program,Verify thru GAO-Bridge`，Generic Flash，0x000000，2.5 MHz。以写入校验成功及断电后实测恢复为通过依据。下面SRAM对照步骤用于复现历史实验，断电不保留配置；串口使用当前实际端口，最新为COM3。

## 证据

用户的 amplitude_code=112、baseline_code=16、period_us=2000、decay_us=12 测试，在 50 MSa/s 下看到起始约1 μs深尖峰，以及恢复段的一次额外下跳。视频抽查0/4/8/12/16/20秒画面，均出现相同位置的异常。111码对照终端确认参数正确；起始深尖峰消失，Vpp约2.8V，恢复段额外下跳仍存在。因此不能把全部异常归结为低采样率；根因待实物验证。

## 仅修改 DAC 输出相位

原版 phase=0 时同时拉低时钟并更新数据；phase=25时拉高时钟。诊断版将数据更新移到phase=10：

```text
每1 μs：
0 ns       CLK下降
200 ns     DATA更新
500 ns     CLK上升
1000 ns    下一次CLK下降
```

RTL正常运行中，上升沿前数据稳定300ns，下降沿前稳定700ns，数据变化距前一时钟边沿至少200ns。复位为独立控制事件，不作为正常采样边沿保证。两种时钟边沿都与数据变化分开，实际DAC采样沿仍需对应模块原理图/芯片资料确认。本实验不能独立证明采样沿或器件级时序满足要求。

SPI协议、H5/H6接线、1MSPS、参数和STM32 HEX均与原通信联调版一致。峰值、周期和指数递推算法没有修改。编译布局变化也可能影响实验结果，改善只能支持接口时序方向，不能单凭一次对照确定根因。

## 下载及对照

Gowin Programmer选择本目录 `impl/pnr/g1_dac_spi.fs`，SRAM Program。保持现有接线。下载后按STM32 RST，再从stm32_firmware终端执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\tools\run_bench.ps1" -Port COM4 -PeriodUs 2000 -AmplitudeCode 112 -Seconds 60
```

示波器5us/div、1V/div、普通采样、50MSa/s、下降沿触发约1.48V，电位器和负载不变。检查起始深尖峰和恢复段下跳是否消失；正常主脉冲幅度应约2.8V，准确电压未标定。原版本可由原目录FS恢复；勿直接覆盖原文件。

## 验证

Gowin综合、布局布线和码流生成通过，50MHz内部setup/hold违例均0，setup最差slack8.385ns。XSim通过162项功能检查及22300次DAC上升沿setup检查；新增正常运行下降沿setup至少700ns、数据对前一边沿hold至少200ns断言通过。临时仿真目录已清理。后续板级验收结果见上方记录；本次文档整理未重新运行编译或测试。

源码：`rtl/g1_dac_spi.v`；复现脚本：`scripts/build.ps1`及`scripts/simulate.ps1`；报告：`reports/build.log`、`reports/simulation.log`、`impl/pnr/g1_dac_spi.tr`。
