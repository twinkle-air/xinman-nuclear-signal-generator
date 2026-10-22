# 公开发布前复核（2026-10-22）

复核在独立发布副本中进行，无真实串口操作或硬件烧录。

|检查|结果|证据|
|---|---|---|
|Python编译|compileall通过|launcher.py、src、tests|
|PC自动测试|56 passed|pc_tests.log|
|当前EXE启动自检|V0.10.3通过|exe_smoke_result.json|
|STM32 N4交叉编译|生成ELF/HEX/BIN，text48640/data476/bss9996|stm32_configure.log、stm32_build.log|
|STM32主机mock检查|92 checks通过|stm32_host_tests.log|
|FPGA RTL及testbench编译/展开|通过|fpga_compile.log|
|SPI仿真|162 checks，22298 DAC setup checks|tb_spi.log|
|Nuclear V3仿真|18540 checks|tb_nuclear.log|
|Competition V4仿真|37091 checks，50494 DAC clocks|tb_competition.log|

STM32链接器对未实现的newlib系统调用给出既有warning；编译链接退出码0，日志原样保留。本次未重跑Gowin完整布局布线，既有FS及对应构建/时序报告随工程发布。历史版本依赖其既有报告，不声称本次逐个重新构建。

密钥扫描：公开候选文本未命中常见GitHub/OpenAI token或私钥模式，无.env/私钥文件；这是模式检查，不是穷尽安全审计。公开文件未含虚拟环境及本机认证存储。

本地副本CMake等临时目录已被.gitignore排除。自动审批阻止了删除发布副本中历史build-*缓存的操作，因此未绕过删除限制；这些缓存不进入Git或Release。原比赛工作区与冻结包保持不变。

这些编译/仿真结果不扩大实物测试覆盖范围；硬件限制以仓库README和原始实测记录为准。
