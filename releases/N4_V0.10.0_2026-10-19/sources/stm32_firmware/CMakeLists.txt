cmake_minimum_required(VERSION 3.20)
project(nucsignal_f405 C ASM)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
option(NUCLEAR_BENCH "Single-channel nuclear signal build V3" OFF)
option(COMPETITION_BENCH "Single-channel competition build N4 (requires FPGA V4)" OFF)
if(COMPETITION_BENCH)
    set(NUCLEAR_BENCH ON)
endif()
if(NUCLEAR_BENCH)
    set(BASIC_SPI_BENCH ON)
endif()
option(BASIC_SPI_BENCH "Single-channel FPGA/DAC bench build" OFF)

add_executable(${PROJECT_NAME}.elf
    startup/startup_stm32f405xx.s
    vendor/CORE/system_stm32f4xx.c
    vendor/FWLIB/src/misc.c
    vendor/FWLIB/src/stm32f4xx_gpio.c
    vendor/FWLIB/src/stm32f4xx_rcc.c
    vendor/FWLIB/src/stm32f4xx_spi.c
    vendor/FWLIB/src/stm32f4xx_usart.c
    vendor/FWLIB/src/stm32f4xx_flash.c
    vendor/FWLIB/src/stm32f4xx_iwdg.c
    vendor/LCD/lcd_init.c
    vendor/LCD/lcd.c
    vendor/SYSTEM/delay.c
    src/main.c
    src/board.c
    src/transport.c
    src/crc32.c
    src/protocol.c
    src/fpga_link.c
    src/device.c
    src/storage.c
    src/ui.c
    src/interrupts.c
)

target_include_directories(${PROJECT_NAME}.elf PRIVATE
    include
    vendor/CORE
    vendor/FWLIB/inc
    vendor/LCD
    vendor/SYSTEM
)

target_compile_definitions(${PROJECT_NAME}.elf PRIVATE
    STM32F40_41xxx
    USE_STDPERIPH_DRIVER
    HSE_VALUE=8000000
)
if(NUCLEAR_BENCH)
    target_compile_definitions(${PROJECT_NAME}.elf PRIVATE NUCLEAR_BENCH=1)
endif()
if(COMPETITION_BENCH)
    target_compile_definitions(${PROJECT_NAME}.elf PRIVATE COMPETITION_BENCH=1)
endif()
if(BASIC_SPI_BENCH)
    target_compile_definitions(${PROJECT_NAME}.elf PRIVATE BASIC_SPI_BENCH=1 DEVELOPMENT_BYPASS_SAFETY_INPUTS=1)
    target_link_libraries(${PROJECT_NAME}.elf PRIVATE m)
endif()

target_compile_options(${PROJECT_NAME}.elf PRIVATE
    -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard
    -ffunction-sections -fdata-sections -Wall -Wextra -Werror
    $<$<CONFIG:Debug>:-Og;-g3>
    $<$<CONFIG:Release>:-Os>
)

# The 2014 vendor SPL/LCD example predates GCC 14 and contains legacy
# initializer/indentation warnings. Keep application code on -Werror while
# treating the imported, unmodified vendor sources as third-party code.
set_source_files_properties(
    vendor/CORE/system_stm32f4xx.c
    vendor/FWLIB/src/misc.c
    vendor/FWLIB/src/stm32f4xx_gpio.c
    vendor/FWLIB/src/stm32f4xx_rcc.c
    vendor/FWLIB/src/stm32f4xx_spi.c
    vendor/FWLIB/src/stm32f4xx_usart.c
    vendor/FWLIB/src/stm32f4xx_flash.c
    vendor/FWLIB/src/stm32f4xx_iwdg.c
    vendor/LCD/lcd_init.c
    vendor/LCD/lcd.c
    vendor/SYSTEM/delay.c
    PROPERTIES COMPILE_OPTIONS "-Wno-error"
)

target_link_options(${PROJECT_NAME}.elf PRIVATE
    -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard
    -T${CMAKE_CURRENT_SOURCE_DIR}/linker/STM32F405RGTx_FLASH.ld
    -Wl,--gc-sections -Wl,-Map=${PROJECT_NAME}.map
    -u _printf_float
    --specs=nano.specs --specs=nosys.specs
)

add_custom_command(TARGET ${PROJECT_NAME}.elf POST_BUILD
    COMMAND ${CMAKE_OBJCOPY} -O ihex $<TARGET_FILE_NAME:${PROJECT_NAME}.elf> ${PROJECT_NAME}.hex
    COMMAND ${CMAKE_OBJCOPY} -O binary $<TARGET_FILE_NAME:${PROJECT_NAME}.elf> ${PROJECT_NAME}.bin
    COMMAND ${CMAKE_SIZE} $<TARGET_FILE_NAME:${PROJECT_NAME}.elf>
    WORKING_DIRECTORY $<TARGET_FILE_DIR:${PROJECT_NAME}.elf>
)
