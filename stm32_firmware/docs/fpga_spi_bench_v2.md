# 基础方案通信联调协议V2

仅适用于`F405-B2.0.0`与`g1_dac_spi`，版本寄存器必须为`0x00020000`，能力寄存器必须为单通道1。不能与V1的浮点双通道参数包混用。V1接口文件保留供原方案参考。

SPI1 Mode 0、MSB first、84 MHz APB2除以128，即656.25 kHz；CS低有效。事务仍为`CMD | ADDR_LE16 | LEN_LE16 | DATA(N) | CRC32_LE32 | ACK`，MCU在DATA、CRC和ACK期间持续产生时钟。读请求DATA阶段MCU发送0，FPGA同时返回DATA；写请求返回的数据忽略。CRC32使用ISO-HDLC/zlib：反射多项式0xEDB88320、初值0xFFFFFFFF、末异或0xFFFFFFFF；读CRC仅覆盖5字节头，写CRC覆盖头与DATA。CRC不校验返回DATA，因此握手重复读取和COMMIT参数回读仍须实测稳定性；未来可升级为响应CRC。

CS下降至首个SCK、最后ACK上升沿至CS上升、CS高间隔均需大于1 μs。FPGA在完整ACK字节的最后上升沿收到后应用写操作；中途拉高CS丢弃未完成事务。ACK成功0x79，失败0x1F。CRC/地址/长度/参数错误没有写副作用。

| 地址 | 读/写长度 | 内容 |
| --- | --- | --- |
| 0x0000 | R4 | 魔数0x4E534647，线上小端字节47 46 53 4E |
| 0x0004 | R4 | 版本0x00020000 |
| 0x0008 | R4 | 物理输出通道数1 |
| 0x0010 | W4 | 1=COMMIT、2=START、4=STOP；仅接受单独命令值 |
| 0x0020 | R32 | 沿用fpga_status_t：clip[2]、event[2]、pileup[2]、generation、error_flags；仅CH1 event有实现，其他计数0 |
| 0x0040 | W4 | 待提交generation，运行时拒绝写 |
| 0x0048 | R4 | bit0=running，bit1=committed |
| 0x0100 | R8/W8 | CH1影子参数；运行时拒绝写 |
| 0x0108 | R8 | CH1生效参数 |

只接受表中整块地址及长度。CMD_READ=0x10、CMD_WRITE=0x20；流式CMD=0x30、CH2、预设和数据FIFO不支持，返回失败。只读块在收到完整头时冻结快照。

## CH1参数8字节

| 字节 | 类型 | 定义 |
| --- | --- | --- |
| 0 | u8 | enabled，0或1 |
| 1 | u8 | DAC基线码，0～255 |
| 2 | u8 | 相对基线的正码差，基线+码差≤255 |
| 3 | u8 | 保留，必须0 |
| 4～5 | LE u16 | 周期，128～10000 μs，1 μs步进 |
| 6～7 | LE u16 | alpha=round(exp(−1/τ_us)×65536)，范围24109～64884 |

MCU额外限制τ为1～100 μs，周期至少5τ，固定周期单指数，无噪声、无叠加、无随机事件。默认`01 10 E0 00 E8 03 88 EB`，对应基线16、幅度码差224、1000 μs、alpha60296（约12 μs）。τ=24 μs时alpha62861。

STM32内部channel_config_t保留原结构布局，使用`code / BENCH_CODE_SCALE`暂存码值；这一缩放只是代码兼容表示，不是电压校准。PC联调接口拒绝amplitude_v/baseline_v，仅接受dac_amplitude_code/dac_baseline_code；界面标示码值，HELLO公布UNCALIBRATED-CODES。

影子写入清除committed；COMMIT仅在停止状态生效，更新全部活动参数与generation。START需committed且无超时错误；STOP回到活动基线并清超时标记，不清generation。STOP后MCU需再次COMMIT才能从IDLE重新START。复位清除参数/generation/committed。运行时250 ms未收到成功完整事务，FPGA自行停止并置error_flags bit0和IRQ。该停止机制仍须实物验收。

PC串口帧格式保持protocol_v1.md；SET_PARAM新增码值字段，周期沿用mean_interval_us、τ沿用decay_us。新增0x0070恢复命令执行probe+STOP，将MCU恢复到IDLE；不会自动启动。GET_STATUS中的A/B/PG为null并标明safety_bypass=true，不能当作真实检测通过。
