`timescale 1ns/1ps
module tb_dual_stage1;
reg clk=0; always #10 clk=~clk;
reg reset=1;
reg [1:0] mode_a=0,mode_b=0;
wire [13:0] a,b;
wire ac,aw,bc,bw;
dual_dac_test_core dut(clk,reset,mode_a,mode_b,a,b,ac,aw,bc,bw);
reg [1:0] keys=3;
wire [13:0] board_a,board_b;
wire board_ac,board_aw,board_bc,board_bw;
g1_dual_dac_stage1 #(.DEBOUNCE_CYCLES(10)) board(clk,keys,board_a,board_b,board_ac,board_aw,board_bc,board_bw);
reg monitor=0;
time changed_a=0,changed_b=0,wrt_a=0,wrt_b=0,last_clk=0;
reg [13:0] latched_a,latched_b;
integer i,va,vb,expected_a,expected_b,samples=0;
real decay;
always @(a) begin
    if(monitor && wrt_a!=0 && $time-wrt_a<500) $fatal(1,"A hold violation");
    changed_a=$time;
end
always @(b) begin
    if(monitor && wrt_b!=0 && $time-wrt_b<500) $fatal(1,"B hold violation");
    changed_b=$time;
end
always @(posedge aw) begin
    if(monitor && $time-changed_a<500) $fatal(1,"A setup violation");
    wrt_a=$time; latched_a=a;
end
always @(posedge bw) begin
    if(monitor && $time-changed_b<500) $fatal(1,"B setup violation");
    wrt_b=$time; latched_b=b;
end
always @(posedge ac) begin
    #1;
    if(monitor) begin
        if($time-wrt_a!=101 || $time-wrt_b!=101) $fatal(1,"CLK after WRT phase error");
        if(last_clk!=0 && $time-last_clk!=1000) $fatal(1,"DAC period error");
        if(ac!==bc || aw!==bw || a!==latched_a || b!==latched_b) $fatal(1,"dual latch error");
        last_clk=$time;
    end
end
task sample(output integer av,output integer bv);
begin @(posedge ac); #2; av=a; bv=b; samples=samples+1; end
endtask
task choose(input [1:0] ma,input [1:0] mb);
begin
    @(negedge clk); mode_a=ma; mode_b=mb;
    while(dut.ch1.active_mode!=ma || dut.ch2.active_mode!=mb) @(negedge clk);
end
endtask
task press;
begin @(negedge clk);keys[0]=0; repeat(30) @(negedge clk);
keys[0]=1; repeat(30) @(negedge clk);end
endtask
initial begin
    repeat(4) @(negedge clk); reset=0;monitor=1;
    for(i=0;i<8;i=i+1) begin
        sample(va,vb); if(va!=8192 || vb!=8191) $fatal(1,"fixed code error");
    end
    choose(1,1);
    for(i=0;i<1300;i=i+1) begin
        sample(va,vb);
        if(va!=(i*16)%16384 || vb!=16383-(i*32)%16384) $fatal(1,"ramp wrap/B polarity error at %0d",i);
    end
    choose(2,2);
    for(i=0;i<3000;i=i+1) begin
        sample(va,vb);
        decay=4096.0*$exp(-1.0*(i%1000)/12.0);
        expected_a=(i%1000<128)?8192+$rtoi(decay+0.5):8192;
        decay=3072.0*$exp(-1.0*(i%1500)/24.0);
        expected_b=(i%1500<128)?8192+$rtoi(decay+0.5):8192;
        if(va!=expected_a || vb!=16383-expected_b) $fatal(1,"independent pulse period/LUT error at %0d",i);
    end
    // Change only A. B must continue its pulse stream without restarting.
    choose(0,2);
    for(i=0;i<40;i=i+1) begin
        sample(va,vb);
        decay=3072.0*$exp(-1.0*(i%1500)/24.0);
        if(va!=8192 || vb!=16383-(8192+$rtoi(decay+0.5))) $fatal(1,"channel independence error");
    end
    choose(1,0);
    for(i=0;i<40;i=i+1) begin
        sample(va,vb);
        if(va!=i*16 || vb!=8191) $fatal(1,"mixed-mode error");
    end
    monitor=0; @(negedge clk);reset=1; @(negedge clk);
    if(a!=8192 || b!=8191 || ac!=0 || aw!=0 || bc!=0 || bw!=0) $fatal(1,"reset error");
    keys[0]=0;repeat(3) @(negedge clk);keys[0]=1;repeat(20) @(negedge clk);
    if(board.mode!=0) $fatal(1,"bounce error");
    press();if(board.mode!=1) $fatal(1,"key ramp error");
    keys[0]=0;repeat(100) @(negedge clk);
    if(board.mode!=2) $fatal(1,"held key repeated");
    keys[0]=1;repeat(30) @(negedge clk);
    press();if(board.mode!=0) $fatal(1,"mode wrap error");
    keys[1]=0;repeat(10) @(negedge clk);
    if(board.mode!=0 || board_a!=8192 || board_b!=8191 || board_aw!=0 || board_ac!=0) $fatal(1,"board reset error");
    $display("PASS: %0d dual-channel samples; 14-bit wrap, independent modes/periods, B polarity, 1 MHz WRT/CLK, setup/hold, keys/reset",samples);
    $finish;
end
initial begin #6000000;$fatal(1,"timeout");end
endmodule
