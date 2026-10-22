# MCU–FPGA SPI接口 V1

2026-10-11新增基础方案通信联调配置：使用独立[V2码值协议](fpga_spi_bench_v2.md)，单通道8字节定点参数，不能与本文件的V1双通道浮点包混用。默认Release保留V1；build-bench使用V2。

这是 STM32 固件已经实现的控制面接口。FPGA RTL 必须实现同一接口后，整机功能才能真实联调。

## 电气与模式

- SPI1，Mode 0，MSB first，当前分频后约 10.5 MHz。
- PA4=CS、PA5=SCK、PA6=MISO、PA7=MOSI。
- PC4=READY（高有效）、PC5=IRQ（高有效）、PC3=RESET（高有效运行）。
- 一次事务格式：`CMD(1) | ADDR_LE(2) | LEN_LE(2) | DATA(N) | CRC32_LE(4) | ACK(1)`。
- 写入/流式命令的 CRC32 覆盖头和 DATA；读取命令 CRC32 只覆盖头。
- FPGA 成功返回 `0x79`，失败返回其他值。READY低时MCU不发起事务。

## 命令

| 值 | 含义 |
|---:|---|
| `0x10` | 读取寄存器块 |
| `0x20` | 写入寄存器块 |
| `0x30` | 流式写入数据 |

## 寄存器

| 地址 | 内容 |
|---:|---|
| `0x0000` | 只读魔数 `0x4E534647`（NSFG） |
| `0x0004` | FPGA版本，按 `major.minor.patch` 三个字节编码 |
| `0x0010` | 控制：1=COMMIT、2=START、4=STOP |
| `0x0020` | 状态结构：两路clip/event/pileup计数、generation、error_flags |
| `0x0040` | 待提交generation |
| `0x0100` | CH1影子参数结构 |
| `0x0140` | CH2影子参数结构 |
| `0x0200` | 数据总字节数 |
| `0x0204` | 数据整体CRC32/完成标志 |
| `0x0208` | 数据FIFO；payload前4字节是目标offset，随后最多256字节数据 |
| `0x0210` | 内置模板ID：0=Am-241、1=Cs-137、2=Co-60 |

通道结构使用小端、packed布局，字段定义见 `src/fpga_link.c`。FPGA必须在事件安全边界执行COMMIT，并把成功生效的generation写回状态结构。
