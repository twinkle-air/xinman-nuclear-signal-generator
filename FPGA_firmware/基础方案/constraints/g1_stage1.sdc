# External DAC timing is not signed off until the actual chip is identified.
create_clock -name sys_clk -period 20.000 [get_ports {sys_clk}]
set_false_path -from [get_ports {key_n[0] key_n[1]}]
