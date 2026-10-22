`timescale 1ns/1ps
module tb_competition;
 reg clk=0; always #10 clk=~clk;
 reg reset_n=0, key_stop_n=1, cs=1, sck=0, mosi=0;
 wire miso,ready,irq,dclk; wire [7:0] data;
 g1_dac_spi #(.WATCHDOG_CYCLES(1250000)) dut(clk,key_stop_n,reset_n,cs,sck,mosi,miso,ready,irq,data,dclk);
 byte unsigned tx[0:63], rx[0:63]; byte unsigned ack,tmp;
 integer checks=0,n;
 time last_data_change=0;
 integer clock_checks=0;
 time last_clock_edge=0;
 always @(dclk) last_clock_edge=$time;
 always @(data) if(ready && $time>11000) begin
  if($time-last_clock_edge<200) $fatal(1,"DAC hold below 200 ns");
 end
 always @(negedge dclk) if(ready && $time>11000) begin
  if($time-last_data_change<700) $fatal(1,"DAC falling setup below 700 ns");
 end
 always @(data) last_data_change=$time;
 always @(posedge dclk) if(ready) begin
  if($time-last_data_change<300) $fatal(1,"DAC rising data setup below 300 ns");
  clock_checks++;
 end
 function automatic [31:0] crc_byte(input [31:0] prev,input byte unsigned b);
  reg [31:0] c; begin c=prev^{24'b0,b}; for(int k=0;k<8;k++) c=c[0]?(c>>1)^32'hedb88320:c>>1; return c; end
 endfunction
 task automatic check(input bit ok,input string message);
  if(!ok) $fatal(1,"FAIL: %s",message); checks++;
 endtask
 task automatic transfer(input byte unsigned out_b,output byte unsigned in_b);
  in_b=0;
  for(int j=7;j>=0;j--) begin
   mosi=out_b[j]; #760; sck=1; #100; in_b[j]=miso; #660; sck=0;
  end
  #160;
 endtask
 task automatic transaction(input byte unsigned cmd,input [15:0] addr,input integer len,input bit bad_crc=0);
  reg [31:0] crc; byte unsigned h[0:4];
  h[0]=cmd; h[1]=addr[7:0]; h[2]=addr[15:8];h[3]=len;h[4]=len>>8;
  crc=32'hffffffff; cs=0; #200;
  for(int j=0;j<5;j++) begin transfer(h[j],tmp); crc=crc_byte(crc,h[j]); end
  for(int j=0;j<len;j++) begin transfer(cmd==8'h10 ? 0 : tx[j],rx[j]); if(cmd!=8'h10) crc=crc_byte(crc,tx[j]); end
  crc=~crc; if(bad_crc) crc=crc^1;
  for(int j=0;j<4;j++) transfer((crc>>(8*j))&255,tmp);
  transfer(0,ack); #300; cs=1; #300;
 endtask
 task automatic write_control(input byte unsigned control);
  tx[0]=control;tx[1]=0;tx[2]=0;tx[3]=0;
  transaction(8'h20,16'h10,4);check(ack==8'h79,"control ACK");
 endtask
 task automatic parameters(input byte unsigned amplitude,input integer period,input [15:0] alpha);
  tx[0]=1;tx[1]=16;tx[2]=amplitude;tx[3]=0;
  tx[4]=period&255;tx[5]=period>>8;tx[6]=alpha[7:0];tx[7]=alpha[15:8];
  transaction(8'h20,16'h100,8);check(ack==8'h79,"parameter ACK");
 endtask
 task automatic generation(input integer gen);
  for(int j=0;j<4;j++) tx[j]=(gen>>(8*j))&255;
  transaction(8'h20,16'h40,4);check(ack==8'h79,"generation ACK");write_control(1);
 endtask


 reg [7:0] expected[0:36999];
 task automatic run_case(input integer id,base,amp,period,alpha,random_mode,noise,options,seed,offset,count,events,clips);
  reg [31:0] probability;
  begin
   write_control(4);
   tx[0]=1;tx[1]=base;tx[2]=amp;tx[3]=0;
   tx[4]=period;tx[5]=period>>8;tx[6]=alpha;tx[7]=alpha>>8;
   transaction(8'h20,16'h100,8);check(ack==8'h79,"N4 params ACK");
   probability=64'd4294967296/period;
   tx[0]=random_mode;tx[1]=noise;tx[2]=0;tx[3]=options;
   for(int j=0;j<4;j++)begin tx[j+4]=probability>>(8*j);tx[j+8]=seed>>(8*j);end
   transaction(8'h20,16'h110,12);check(ack==8'h79,"N4 ext ACK");
   transaction(8'h10,16'h110,12);check(ack==8'h79 && rx[3]==options,"N4 options readback");
   generation(id);
   fork
    begin
     @(posedge dut.running);
     for(int k=0;k<count;k++)begin
      @(posedge clk);while(dut.phase!=10)@(posedge clk);
      #1;check(data===expected[offset+k],$sformatf("N4 case %0d sample %0d actual %0d expected %0d",id,k,data,expected[offset+k]));
      @(posedge clk);
     end
    end
    begin write_control(2);end
   join
   check(dut.event_count==events,"N4 event counter");
   check(dut.clip_count==clips,"N4 clipping counter");
   write_control(4);repeat(2)@(posedge dclk);check(data==base,"N4 STOP quiet baseline");
  end
 endtask
 initial begin
  $readmemh("../tb/competition_expected.hex",expected);
  for(int j=0;j<64;j++)tx[j]=0;
  #10000;reset_n=1;#1000;
  transaction(8'h10,4,4);check(rx[2]==4,"V4 identity");
  run_case(1,96,84,20,39750,0,0,0,1,0,2000,100,0);
  run_case(2,96,84,10,24109,0,0,0,1,2000,2000,200,0);
  run_case(3,96,84,1000,65083,0,0,0,1,4000,3000,3,0);
  run_case(4,128,0,1000,60296,0,0,1,1,7000,6000,6,0);
  run_case(5,128,0,1000,60296,0,1,1,1,13000,6000,6,0);
  run_case(6,128,0,1000,60296,0,5,1,1,19000,6000,6,0);
  run_case(7,128,0,1000,60296,0,20,1,1,25000,6000,6,55);
  run_case(8,96,84,128,65086,1,20,1,17,31000,6000,54,1272);
  // Gaussian RMS outside 0..20 is rejected without changing shadow registers.
  tx[0]=0;tx[1]=21;tx[2]=0;tx[3]=1;tx[4]=0;tx[5]=0;tx[6]=0;tx[7]=2;
  tx[8]=1;tx[9]=0;tx[10]=0;tx[11]=0;
  transaction(8'h20,16'h110,12);check(ack==8'h1f,"reject Gaussian RMS21");
  key_stop_n=0;#1000;check(!dut.running && data==16,"N4 local reset");
  $display("PASS: competition V4 %0d checks; DAC clocks %0d",checks,clock_checks);$finish;
 end
endmodule
