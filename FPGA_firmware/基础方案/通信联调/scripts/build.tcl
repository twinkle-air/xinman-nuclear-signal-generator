set root [file normalize [file join [file dirname [info script]] ..]]
cd $root
open_project g1_dac_spi.gprj
set_option -top_module g1_dac_spi
set_option -output_base_name g1_dac_spi
set_option -synthesis_tool gowinsynthesis
set_option -verilog_std v2001
set_option -gen_text_timing_rpt 1
set_option -gen_io_cst 1
set_option -unused_pin default
set_option -use_jtag_as_gpio 0
run all

