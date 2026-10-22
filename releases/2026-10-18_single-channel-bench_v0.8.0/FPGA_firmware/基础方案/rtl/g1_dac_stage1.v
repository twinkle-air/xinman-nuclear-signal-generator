`timescale 1ns/1ps
module g1_dac_stage1 #(
    parameter integer DEBOUNCE_CYCLES = 500000
)(input wire sys_clk, input wire [1:0] key_n,
  output wire [7:0] dac_data, output wire dac_clk);
// Gowin supports register configuration initial values. Hold reset for 256 clocks.
reg [8:0] startup = 0;
reg [1:0] key_meta = 2'b11, key_sync = 2'b11;
reg key_stable = 1, key_previous = 1;
reg [19:0] debounce_count = 0;
reg [1:0] mode = 0;
wire reset = !startup[8] || !key_sync[1];
always @(posedge sys_clk) begin
    if (!startup[8]) startup <= startup + 1'b1;
    key_meta <= key_n;
    key_sync <= key_meta;
    if (reset) begin
        key_stable <= 1; key_previous <= 1;
        debounce_count <= 0; mode <= 0;
    end else begin
        key_previous <= key_stable;
        if (key_sync[0] == key_stable) debounce_count <= 0;
        else if (debounce_count == DEBOUNCE_CYCLES-1) begin
            key_stable <= key_sync[0]; debounce_count <= 0;
        end else debounce_count <= debounce_count + 1'b1;
        if (key_previous && !key_stable) begin
            if (mode == 2) mode <= 0;
            else mode <= mode + 1'b1;
        end
    end
end
dac_test_core core(.sys_clk(sys_clk), .reset(reset), .requested_mode(mode),
                   .dac_data(dac_data), .dac_clk(dac_clk));
endmodule
