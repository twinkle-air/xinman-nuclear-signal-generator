# 发布范围

2026-10-22制作独立公开快照，原工作区和原冻结包未改动。所有项目代码、技术文档、历次方案、原始CSV和截图保留。虚拟环境、构建缓存、IDE用户状态不入Git；STM32既有产物另存firmware_artifacts。大于40MB的EXE和ZIP作为Release附件，见release_assets.json。冻结包旧manifest保留原样，原路径与附件映射另列。

scope_csv_103_13.csv原始文件未归档，scope_csv_102_0.csv疑似不完整，均不补造原始数据或冒充定量验证通过。当前交付仅单通道单指数。

源码和原始测试文件按字节保留；新增README、许可、发布复核是本次整理入口。FILES_SHA256.csv列公开文件SHA256，清单自身和Git内部文件不自我包含。excluded_paths.json记录整理时排除目录；.gitignore另排除CMake build-*。
