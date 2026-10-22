`timescale 1ns/1ps
module dual_dac_test_core #(
    parameter integer CLOCK_DIV = 50,
    parameter integer CH1_PERIOD = 1000,
    parameter integer CH2_PERIOD = 1500,
    parameter integer CH2_INVERT = 1
)(input wire sys_clk, input wire reset, input wire [1:0] mode_a, mode_b,
  output wire [13:0] dac_a_data, dac_b_data,
  output reg dac_a_clk = 0, dac_a_wrt = 0, dac_b_clk = 0, dac_b_wrt = 0);
reg [15:0] phase = 0;
// Defaults: data at 0 ns, WRT rising at 500 ns, CLK rising at 600 ns.
// Delayed CLK avoids the datasheet's ambiguous near-simultaneous separate pins.
wire sample_enable = phase == 0;
wave_source_14 #(.SHAPE_ID(0), .PERIOD_SAMPLES(CH1_PERIOD), .RAMP_STEP(16)) ch1(
    sys_clk,reset,sample_enable,mode_a,dac_a_data);
// The KY module manual states channel B's analog transfer is inverted.
wave_source_14 #(.SHAPE_ID(1), .PERIOD_SAMPLES(CH2_PERIOD), .RAMP_STEP(32),
    .INVERT_OUTPUT(CH2_INVERT)) ch2(sys_clk,reset,sample_enable,mode_b,dac_b_data);
always @(posedge sys_clk) begin
    if (reset) begin
        phase <= 0; dac_a_clk <= 0; dac_a_wrt <= 0; dac_b_clk <= 0; dac_b_wrt <= 0;
    end else begin
        if (phase == CLOCK_DIV-1) phase <= 0;
        else phase <= phase+1'b1;
        if (phase == 0) begin dac_a_wrt <= 0; dac_b_wrt <= 0; end
        if (phase == CLOCK_DIV/10) begin dac_a_clk <= 0; dac_b_clk <= 0; end
        if (phase == CLOCK_DIV/2) begin dac_a_wrt <= 1; dac_b_wrt <= 1; end
        if (phase == CLOCK_DIV/2+CLOCK_DIV/10) begin dac_a_clk <= 1; dac_b_clk <= 1; end
    end
end
endmodule
