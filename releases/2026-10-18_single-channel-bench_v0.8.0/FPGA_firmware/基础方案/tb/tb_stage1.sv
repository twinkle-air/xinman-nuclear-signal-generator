`timescale 1ns/1ps
module tb_stage1;
reg clk=0;
always #10 clk=~clk;
reg reset=1;
reg [1:0] mode=0;
wire [7:0] data;
wire dclk;
dac_test_core dut(clk,reset,mode,data,dclk);
reg [1:0] keys=3;
wire [7:0] board_data;
wire board_clk;
g1_dac_stage1 #(.DEBOUNCE_CYCLES(10)) board(clk,keys,board_data,board_clk);
time changed=0, last_edge=0;
integer checked=0, i, previous, expected;
real decay;
reg monitor=0;
always @(data) changed=$time;
always @(posedge dclk) begin
    #1;
    if (monitor) begin
        if ($time-changed < 500) $fatal(1,"data setup below 500 ns");
        if (last_edge != 0 && $time-last_edge != 1000) $fatal(1,"sample period error");
        last_edge=$time;
    end
end
task sample(output integer value);
begin @(posedge dclk); #2; value=data; checked=checked+1; end
endtask
task choose(input [1:0] m);
begin
    @(negedge clk); mode=m;
    while (dut.active_mode != m) @(negedge clk);
end
endtask
task press;
begin
    @(negedge clk); keys[0]=0;
    repeat(30) @(negedge clk);
    keys[0]=1;
    repeat(30) @(negedge clk);
end
endtask
initial begin
    repeat(4) @(negedge clk);
    reset=0; monitor=1;
    for(i=0;i<8;i=i+1) begin
        sample(expected);
        if(expected != 128) $fatal(1,"fixed code error");
    end
    choose(1);
    for(i=0;i<300;i=i+1) begin
        sample(expected);
        if(expected != (i%256)) $fatal(1,"ramp wrap error at %0d: %0d",i,expected);
    end
    choose(2);
    for(i=0;i<2000;i=i+1) begin
        sample(expected);
        if(i%1000 < 64) begin
            decay=224.0*$exp(-1.0*(i%1000)/12.0);
            if(expected != 16+$rtoi(decay+0.5)) $fatal(1,"pulse LUT mismatch at %0d",i);
        end else if(expected != 16) $fatal(1,"pulse baseline error");
    end
    choose(0); sample(expected);
    if(expected != 128) $fatal(1,"mode return error");
    monitor=0;
    @(negedge clk); reset=1;
    @(negedge clk);
    if(data != 128 || dclk != 0) $fatal(1,"reset error");
    reset=0;
    if(board.mode != 0) $fatal(1,"powerup mode error");
    // A short bounce must not select a waveform.
    keys[0]=0; repeat(3) @(negedge clk);
    keys[0]=1; repeat(20) @(negedge clk);
    if(board.mode != 0) $fatal(1,"debounce failed");
    press(); if(board.mode != 1) $fatal(1,"key ramp selection failed");
    // Holding the key must cause only one mode change.
    keys[0]=0; repeat(100) @(negedge clk);
    if(board.mode != 2) $fatal(1,"held key repeated");
    keys[0]=1; repeat(30) @(negedge clk);
    press(); if(board.mode != 0) $fatal(1,"key mode wrap failed");
    keys[1]=0; repeat(10) @(negedge clk);
    if(board.mode != 0 || board_data != 128 || board_clk != 0) $fatal(1,"board reset failed");
    $display("PASS: %0d DAC samples; fixed/ramp/pulse, 1 MHz, setup, startup, bounce, held key, reset",checked);
    $finish;
end
initial begin #4000000; $fatal(1,"timeout"); end
endmodule
