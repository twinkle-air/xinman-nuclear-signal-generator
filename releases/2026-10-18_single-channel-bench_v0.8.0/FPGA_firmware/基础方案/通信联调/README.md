# 基础方案通信联调版

日期：2026-10-11。FPGA-G1/GW2A-LV18PG256C8/I7 + ATK-MO8008 V3.3，单通道8位DAC，1 MSPS。上级目录中的按键版保持原样；本目录是独立Gowin工程，双通道进阶工程不受本次修改影响。

## 产物

- FPGA工程：`g1_dac_spi.gprj`；顶层：`g1_dac_spi`。
- FPGA码流：`impl/pnr/g1_dac_spi.fs`。
- 匹配STM32固件：`../../../stm32_firmware/build-bench/nucsignal_f405.hex`，勿混用默认Release。
- [新增连接表](连接表.md)；[完整下载及联调步骤](../../../stm32_firmware/docs/基础方案通信联调.md)。

## 行为

上电/外部RESET_N低/停止键按下时，运行标志清零，DAC保持基线码16。MCU完成COMMIT后才能START；STOP回到生效的基线码，最迟在下一次1 μs更新点改变数据，随后DAC上升沿采样。基线码不等于0 V。

参数为使能、基线码、脉冲码差、周期（整数μs）、指数系数（Q0.16）。初始为16/224/1000 μs/12 μs。FPGA使用24位内部Q8.16幅度累加器，每1 μs乘一次Q0.16系数，输出舍入为8位。相对原64点码表，本版为递推指数，尾部继续衰减到基线；不能把新码流当成旧按键版完全相同的波形。

参数仅允许在停止状态写入/提交；影子写入不改变生效参数。COMMIT回写generation，STM32同时核对generation与8字节生效参数回读。不实现随机到达、噪声、双指数、能谱或任意波形上传，相关请求拒绝。

SPI Mode 0，MSB first，656.25 kHz；50 MHz同步采样SPI，当前支持上限按1 MHz联调约束使用。MCU在CS两侧保留大于1 μs间隔。CRC32错误、无效地址/参数与未完成ACK的事务不改变寄存器。读状态为事务头结束时的快照。

MCU每100 ms读取FPGA状态；FPGA连续250 ms没有成功完整事务会停止并拉高IRQ。PC连续2 s没有有效新请求时，MCU尝试停止并锁存错误。断开MISO时MCU状态查询失败并尝试STOP；若同时断开控制链路，FPGA自身超时停止。整机实测仍需分别验证。

## 编译与检查

在本目录执行：

```powershell
.\scripts\open_project.ps1
.\scripts\build.ps1
.\scripts\simulate.ps1
```

Gowin综合、布局布线与码流生成通过；50 MHz内部setup/hold违例均0，最差setup slack 7.353 ns、hold slack 0.328 ns。资源890逻辑、609寄存器、2个MULTALU36X18；内部Fmax 79.071 MHz不代表DAC采样率。18个端口约束已复核。

XSim通过162项功能检查及22300次DAC数据至少500 ns稳定时间检查：魔数/版本/单通道能力、CRC、影子和生效参数、generation、START/STOP、1000/2000 μs周期、固定点指数样点、运行中拒绝写参数、断帧恢复、超时与按键复位。仿真将250 ms超时缩为10 ms以缩短运行时间。

外部SPI板间时序、同步器亚稳态概率与DAC器件级setup/hold未完成签核；需要短线低速实物联调。本目录尚未下载到实物或完成新固件模拟输出验收，先前按键版实测不能替代本版验收。
