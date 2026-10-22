create_clock -name sys_clk -period 20.000 [get_ports {sys_clk}]
# Async SPI inputs enter only synchronizer flops. Bench SCK <= 1 MHz.
set_false_path -from [get_ports {spi_cs_n spi_sck spi_mosi reset_n key_stop_n}]
