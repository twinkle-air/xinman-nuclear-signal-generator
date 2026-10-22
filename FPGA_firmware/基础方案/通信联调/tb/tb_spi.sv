`timescale 1ns/1ps
module tb_spi;
 reg clk=0; always #10 clk=~clk;
 reg reset_n=0, key_stop_n=1, cs=1, sck=0, mosi=0;
 wire miso,ready,irq,dclk; wire [7:0] data;
 g1_dac_spi #(.WATCHDOG_CYCLES(500000)) dut(clk,key_stop_n,reset_n,cs,sck,mosi,miso,ready,irq,data,dclk);
 byte unsigned tx[0:63], rx[0:63]; byte unsigned ack,tmp;
 integer checks=0,n;
 time last_data_change=0;
 integer clock_checks=0;
 always @(data) last_data_change=$time;
 always @(posedge dclk) if(ready) begin
  if($time-last_data_change<500) $fatal(1,"DAC data setup below 500 ns");
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
 initial begin
  for(int j=0;j<64;j++)tx[j]=0;
  #10000; reset_n=1; #1000;check(ready,"ready after reset");
  transaction(8'h10,0,4);$display("magic %02x %02x %02x %02x ack %02x",rx[0],rx[1],rx[2],rx[3],ack);
  check(ack==8'h79 && {rx[3],rx[2],rx[1],rx[0]}==32'h4e534647,"magic little endian");
  transaction(8'h10,4,4);check(ack==8'h79 && rx[2]==2,"version V2");
  transaction(8'h10,8,4);check(ack==8'h79 && rx[0]==1,"one channel");
  tx[0]=2; transaction(8'h20,16'h10,4);check(ack!=8'h79,"START rejected before COMMIT");
  parameters(224,1000,60296);generation(42);
  transaction(8'h10,16'h20,32);check(ack==8'h79 && rx[24]==42 && rx[28]==0,"snapshot generation/status");
  transaction(8'h10,16'h108,8);check(ack==8'h79 && rx[2]==224 && {rx[5],rx[4]}==1000,"active readback");
  write_control(2);
  // Compare two complete 1 MHz pulse periods against the fixed-point model.
  begin
   reg [23:0] model; reg [39:0] product; integer idx,previous_peak,seen; integer samples;
   idx=0; seen=0; previous_peak=-1; samples=0; model=0;
   while(seen<2 || idx<64) begin
    @(posedge dclk); #1;
    if(data==240) begin
     if(previous_peak>=0) check(samples-previous_peak==1000,"pulse period 1000 samples");
     previous_peak=samples;seen++;idx=0;model=224<<16;
    end
    if(seen>0 && idx<64) begin
     check(data==16+((model+32768)>>16),"exponential point matches model");
     product=model*60296;model=product>>16;idx++;
    end
    samples++;
   end
  end
  // Heartbeat before checking rejected writes while running.
  transaction(8'h10,16'h20,32);check(ack==8'h79,"heartbeat");
  tx[0]=0; transaction(8'h20,16'h100,8);check(ack!=8'h79,"parameter write rejected while running");
  write_control(4); repeat(2) @(posedge dclk);check(data==16,"STOP to baseline");
  parameters(112,2000,62861);generation(43);write_control(2);
  begin integer samples,peaks,last; samples=0;peaks=0;last=0;
   while(peaks<2) begin @(posedge dclk);#1;
    if(data==128) begin if(peaks>0)check(samples-last==2000,"updated period");last=samples;peaks++;end
    samples++;
   end
  end
  write_control(4);
  // Corrupt CRC, overrange code sum, unsupported register and aborted packet.
  tx[0]=1;tx[1]=16;tx[2]=100;tx[3]=0;tx[4]=232;tx[5]=3;tx[6]=136;tx[7]=235;
  transaction(8'h20,16'h100,8,1);check(ack!=8'h79,"CRC rejection");
  transaction(8'h10,16'h100,8);check(rx[2]==112,"CRC does not mutate shadow");
  tx[0]=1;tx[1]=250;tx[2]=100;tx[3]=0;tx[4]=232;tx[5]=3;tx[6]=136;tx[7]=235;
  transaction(8'h20,16'h100,8);check(ack!=8'h79,"code overflow rejection");
  transaction(8'h20,16'h140,8);check(ack!=8'h79,"CH2 rejected");
  cs=0;#200;transfer(8'h20,tmp);transfer(0,tmp);cs=1;#500;
  transaction(8'h10,0,4);check(ack==8'h79 && rx[0]==8'h47,"abort recovers parser");
  write_control(2);#10100000;repeat(2)@(posedge dclk);check(irq && data==16,"watchdog stops output");
  write_control(4);check(!irq,"STOP clears watchdog fault");
  write_control(2);key_stop_n=0;#1000;check(!ready && !dut.running,"board stop resets control");key_stop_n=1;#1000;
  transaction(8'h10,16'h20,32);check(ack==8'h79 && rx[24]==0,"reset clears generation");
  $display("PASS: SPI bench %0d checks; %0d DAC setup checks",checks,clock_checks);$finish;
 end
 initial begin #25000000;$fatal(1,"simulation timeout");end
endmodule
