# 智能反馈信号发生器 STM32F405 固件

## 基础方案通信联调版（2026-10-11）

新增`BASIC_SPI_BENCH=ON`独立构建，产物在`build-bench`。使用`tools/build_bench.ps1`编译，`tools/flash.ps1 -Profile bench`烧录；操作与新增接线见[通信联调指南](docs/基础方案通信联调.md)。只支持CH1周期指数脉冲，以DAC码值控制幅度；STM32 SPI为656.25 kHz。默认Release配置保留原双通道V1接口及关闭检测旁路。

匹配FPGA工程在`../FPGA_firmware/基础方案/通信联调`。本版编译及模拟测试通过，尚未实物下载；不把按键版已有示波器结果作为本版实测。PC联调脚本使用项目现有pc_app/.venv环境；图形上位机的伏特参数/数据导入功能尚未适配此联调配置。

目标芯片为 STM32F405RGT6，固件全部由 C11 和 Cortex-M4 GNU 汇编组成。PowerShell文件仅用于VS Code构建/烧录，不会运行在单片机上。

## 已实现

- 参考厂商1.8寸TFT例程，沿用ST7735S与PB4–PB9软件SPI接线。
- 板载CH340对应USART1 PA9/PA10，115200 8N1，与PC端`protocol_v1.md`帧格式兼容。
- HELLO、GET_STATUS、SET_PARAM、COMMIT、DATA_BEGIN/CHUNK/END、START、STOP、SELECT_PRESET、READ_HIST、SAVE/LOAD_PROFILE。
- CRC32、分片/粘包处理、SEQ重复请求重放、大数据offset检查和流式转发。
- 双通道影子参数、参数包络检查、COMMIT后更新生效值。
- BOOT/SELF_TEST/IDLE/CONFIGURED/RUNNING/ERROR状态机、安全停止和独立看门狗。
- SPI1 FPGA控制链路、READY流控、状态/计数器读取。
- 内部Flash扇区11持久化四组Profile；链接脚本已保留该扇区。
- TFT以10 Hz局部状态周期显示设备状态、双通道参数、FPGA/PG和错误。

## 首次打开和编译

1. 在VS Code中使用“打开文件夹”打开本目录，不要只打开某个`.c`文件。
2. 安装CMake Tools、STM32 VS Code Extension、C/C++扩展。
3. 按`Ctrl+Shift+B`执行默认任务“STM32: 编译 Release”。
4. 产物位于`build-gcc`：`nucsignal_f405.elf/.hex/.bin`。

当前电脑使用 GNU Arm Embedded Toolchain 14.2.Rel1、CMake和Ninja完成过Release编译。

## 烧录

连接ST-Link的SWDIO、SWCLK、GND、3.3V参考电压及可选NRST。安装STM32CubeProgrammer后，在VS Code运行任务“STM32: ST-Link 烧录”。也可直接使用STM32 VS Code扩展选择`build-gcc/nucsignal_f405.elf`调试。

板载第一路Type-C经CH340连接PA9/PA10，供上位机运行通信；第二路Type-C连接PA11/PA12原生USB。目前固件选择CH340链路，因此无需USB Device驱动。

## 接线与必须确认的边界

- LCD：PB9=MOSI、PB8=SCLK、PB7=CS、PB5=DC、PB4=BLK；PB6为字库芯片MISO。
- FPGA：PA4–PA7与PC3–PC5，详见`docs/fpga_spi_register_map.md`。
- 最终C板的A/B板在位和PG输入暂定PC0/PC1/PC2，均高有效。
- PA0是紧急STOP，PC8/PC9预留本机菜单键。
- 默认安全旁路关闭。仅在无A/B板的桌面调试构建中，才可显式定义`DEVELOPMENT_BYPASS_SAFETY_INPUTS=1`。

编译通过只能证明源码、链接脚本和产物生成正确；屏幕方向、实体按键电平、FPGA SPI时序、板卡在位/PG极性及真实输出仍必须在实物上验证。没有实体板和匹配的FPGA RTL时，不能把这些项目写成“实测通过”。
