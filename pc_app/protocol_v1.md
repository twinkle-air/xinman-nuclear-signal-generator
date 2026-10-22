# PC–STM32 USB CDC协议 V1

本文件冻结PC端当前实现，STM32固件必须与其一致后才能完成真实硬件联调。

## 物理连接

- `USB CDC`：STM32 USB Device配置为CDC虚拟串口。PC端固定115200、8N1；USB CDC本身不依赖实际UART波特率。
- `ST-Link VCP`：必须使用具有VCP功能的ST-Link，并将ST-Link VCP TX/RX与STM32 UART RX/TX交叉连接，同时连接GND。不能只连接SWDIO/SWCLK。
- ST-Link VCP支持115200、460800、921600三档界面选择；STM32 UART必须使用相同波特率。
- 连接后PC首先发送`HELLO`，收到同SEQ且带`ACK`标志的响应才显示“硬件已连接”。

## 帧格式

沿用项目方案：`A5 5A | VER | FLAGS | CMD | SEQ | LENGTH | PAYLOAD | CRC32`，多字节整数均为小端，CRC覆盖`VER..PAYLOAD`。

## Payload约定

- JSON均为UTF-8紧凑JSON。
- `HELLO`请求包含`client/protocol/transport/baudrate`。
- `HELLO` ACK：`{"firmware":"...","fpga":"...","calibration":"..."}`。
- `DATA_BEGIN`：JSON，包含`name/kind/points/encoding/bytes/source_sha256`。
- `DATA_CHUNK`：4字节小端offset，后接最多1000字节数据。
- 信号源数据编码：每点`x,y`两个小端float32，按点交织。
- `DATA_END`：JSON，包含重组数据的`bytes`和`crc32`。
- `SET_PARAM`：JSON，包含`channel`和该通道全部参数。
- `COMMIT/START/STOP`：空payload。
- 所有命令必须返回同CMD、同SEQ的ACK；失败返回`ERROR`，payload为UTF-8错误信息。
- PC超时500 ms后重发，最多3次；MCU必须按SEQ去重。

当前PC端协议已完成并通过伪串口测试；真实硬件验收仍需STM32固件实现并使用实物USB联调。

## V0.8.0单通道台架适配

帧格式保持不变；根据HELLO选择流程。仅`bench=true, channels=1, firmware=F405-B2.0.0`进入已支持的台架模式。未知台架版本或能力矛盾时关闭连接，不尝试通用波形/CH2下发。旧双通道HELLO未带能力字段时维持原V1流程。

- `RECOVER=0x0070`：请求空payload；响应`{"recovered":true}`，随后GET_STATUS须IDLE/OK、fpga=true。
- `SET_PARAM=0x0010`：仅`{"channel":1,"enabled":true,"dac_baseline_code":16,"dac_amplitude_code":224,"mean_interval_us":1000,"decay_us":12}`。幅度为相对基线正码差，基线+幅度≤255；周期128–10000 μs、τ为1–100 μs、周期≥5τ。无`amplitude_v`/`baseline_v`或CH2。
- 提交：RECOVER → GET_STATUS → SET_PARAM(accepted=true) → COMMIT(committed=true) → GET_STATUS，状态CONFIG/OK、fpga=true、generation递增1且回读参数一致后才允许START。
- GET_STATUS：回读`state/error/fpga/generation/dac_baseline_code/dac_amplitude_code/period_us/decay_us/safety_bypass`。A/B/PG为null时显示未检测，不能显示检测通过。
- START后回读须RUN/OK；STOP后回读须IDLE/OK。停止、错误、generation变化或参数回读不符会取消已验证配置，必须重新提交。
- 连接后的所有台架命令和约200 ms状态轮询由同一后台线程串行执行。失联状态标为未知；不会自动START。断开和退出时尝试STOP+回读，失败提示未确认。
- 台架不发送DATA_BEGIN/CHUNK/END，不上传能谱，不设置随机、噪声或CH2。预览和参数只用未校准DAC码，支持的FPGA SPI契约见`../stm32_firmware/docs/fpga_spi_bench_v2.md`。

## ST-Link边界

- `ST-Link TX → STM32 UART_RX`，`ST-Link RX → STM32 UART_TX`，并连接公共GND。
- 普通只提供SWDIO/SWCLK的ST-LINK/V2或兼容下载器没有VCP，软件不会将其显示为可用串口。
- STLINK-V3SET、STLINK-V3MINI/MODS等型号提供VCP UART；具体引脚必须以所用探头和开发板手册为准。
- SWD仍保留给下载和调试，VCP UART负责本项目的运行数据。两者可通过同一ST-Link USB设备提供，但在目标板侧是不同信号。

官方依据：

- STLINK-V3SET用户手册：https://www.st.com/resource/en/user_manual/um2448-stlinkv3set-debuggerprogrammer-for-stm8-and-stm32-stmicroelectronics.pdf
- STLINK-V3MODS/MINI用户手册：https://www.st.com/resource/en/user_manual/dm00555046-stlinkv3mods-and-stlinkv3mini-mini-debuggersprogrammers-for-stm32-stmicroelectronics.pdf
