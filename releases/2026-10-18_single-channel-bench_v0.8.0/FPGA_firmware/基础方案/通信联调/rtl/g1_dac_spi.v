`timescale 1ns/1ps
// Bench protocol V2: all logic clocked by the board's 50 MHz oscillator.
module g1_dac_spi #(parameter WATCHDOG_CYCLES=12500000)(
 input wire sys_clk, input wire key_stop_n, input wire reset_n,
 input wire spi_cs_n, input wire spi_sck, input wire spi_mosi,
 output wire spi_miso, output wire ready, output wire irq,
 output reg [7:0] dac_data=16, output reg dac_clk=0);
 reg [8:0] startup=0;
 reg [2:0] cs=7, sck=0;
 reg [1:0] mosi=0, rst=0, key_stop=3;
 wire reset=!startup[8] || !rst[1] || !key_stop[1];
 always @(posedge sys_clk) begin
  if (!startup[8]) startup<=startup+1'b1;
  cs<={cs[1:0],spi_cs_n}; sck<={sck[1:0],spi_sck};
  mosi<={mosi[0],spi_mosi}; rst<={rst[0],reset_n}; key_stop<={key_stop[0],key_stop_n};
 end
 reg [7:0] shadow_base=16, shadow_amp=224, active_base=16, active_amp=224;
 reg shadow_enable=1, active_enable=1;
 reg [15:0] shadow_period=1000, active_period=1000;
 reg [15:0] shadow_alpha=60296, active_alpha=60296;
 reg [31:0] pending_generation=0, generation=0, event_count=0;
 reg running=0, committed=0, link_error=0;
 reg [31:0] watchdog=0;
 reg [5:0] phase=0;
 reg [15:0] sample_index=0;
 reg [23:0] level=0;
 wire [39:0] decay_product=level*active_alpha;
 wire [39:0] first_decay_product={active_amp,16'b0}*active_alpha;
 wire [8:0] rounded_level={1'b0,level[23:16]}+level[15];
 wire [8:0] output_sum={1'b0,active_base}+rounded_level;
 assign ready=!reset;
 assign irq=link_error;
 reg miso_bit=0;
 assign spi_miso=spi_cs_n ? 1'bz : miso_bit;
 reg [2:0] bit_count=0;
 reg [7:0] rx_shift=0, tx_shift=0, next_tx=0;
 wire [7:0] received={rx_shift[6:0],mosi[1]};
 reg [15:0] pos=0, address=0, length=0;
 reg [7:0] command=0;
 reg [31:0] crc=32'hffffffff, crc_received=0;
 reg [7:0] payload[0:63];
 reg [255:0] read_snapshot=0;
 reg [255:0] read_payload;
 reg frame_ok=0;
 integer i;
 function automatic [31:0] crc_byte;
  input [31:0] previous; input [7:0] value;
  reg [31:0] c; integer k;
  begin c=previous^{24'b0,value};
   for(k=0;k<8;k=k+1) c=c[0] ? (c>>1)^32'hedb88320 : c>>1;
   crc_byte=c;
  end
 endfunction
 always @* begin
  read_payload=0;
  case(address)
   0:read_payload[31:0]=32'h4e534647;
   4:read_payload[31:0]=32'h00020000;
   8:read_payload[31:0]=1;
   16'h20:begin read_payload[95:64]=event_count; read_payload[223:192]=generation;
    read_payload[255:224]={31'b0,link_error}; end
   16'h48:read_payload[31:0]={30'b0,committed,running};
   16'h100:read_payload[63:0]={shadow_alpha,shadow_period,8'b0,shadow_amp,shadow_base,7'b0,shadow_enable};
   16'h108:read_payload[63:0]={active_alpha,active_period,8'b0,active_amp,active_base,7'b0,active_enable};
  endcase
 end
 wire valid_read=(address==0 && length==4) || (address==4 && length==4) ||
  (address==8 && length==4) || (address==16'h20 && length==32) ||
  (address==16'h48 && length==4) || (address==16'h100 && length==8) ||
  (address==16'h108 && length==8);
 wire [15:0] new_period={payload[5],payload[4]};
 wire [15:0] new_alpha={payload[7],payload[6]};
 wire valid_parameters=payload[0]<=1 && payload[3]==0 &&
  ({1'b0,payload[1]}+{1'b0,payload[2]})<=255 &&
  new_period>=128 && new_period<=10000 && new_alpha>=24109 && new_alpha<=64884;
 wire valid_control=length==4 && payload[1]==0 && payload[2]==0 && payload[3]==0 &&
  ((payload[0]==1 && !running) || (payload[0]==2 && committed && !link_error) || payload[0]==4);
 wire valid_write=(address==16'h100 && length==8 && !running && valid_parameters) ||
  (address==16'h40 && length==4 && !running) || (address==16'h10 && valid_control);
 always @(posedge sys_clk) begin
  if(reset) begin
   bit_count<=0; pos<=0; crc<=32'hffffffff; rx_shift<=0; tx_shift<=0; next_tx<=0;
   miso_bit<=0; frame_ok<=0; crc_received<=0; command<=0; address<=0; length<=0;
   shadow_base<=16; shadow_amp<=224; shadow_period<=1000; shadow_alpha<=60296; shadow_enable<=1;
   active_base<=16; active_amp<=224; active_period<=1000; active_alpha<=60296; active_enable<=1;
   pending_generation<=0; generation<=0; event_count<=0;
   running<=0; committed<=0; link_error<=0; watchdog<=0;
   phase<=0; sample_index<=0; level<=0; dac_data<=16; dac_clk<=0;
   read_snapshot<=0;
   for(i=0;i<64;i=i+1) payload[i]<=0;
  end else begin
   if(phase==49) phase<=0; else phase<=phase+1'b1;
   if(phase==25) dac_clk<=1;
   if(phase==0) begin
    dac_clk<=0;
    if(!running || !active_enable) begin dac_data<=active_base; sample_index<=0; level<=0; end
    else if(sample_index==0) begin
     dac_data<=active_base+active_amp; level<=first_decay_product[39:16];
     sample_index<=1; event_count<=event_count+1'b1;
    end else begin
     dac_data<=output_sum>255 ? 255 : output_sum[7:0];
     level<=decay_product[39:16];
     if(sample_index==active_period-1) sample_index<=0; else sample_index<=sample_index+1'b1;
    end
   end
   if(running) begin
    if(watchdog==WATCHDOG_CYCLES-1) begin running<=0; link_error<=1; end
    else watchdog<=watchdog+1'b1;
   end else watchdog<=0;
   // Deasserted CS aborts a partial frame without changing any registers.
   if(cs[2]) begin bit_count<=0; pos<=0; crc<=32'hffffffff; crc_received<=0;
    rx_shift<=0; next_tx<=0; tx_shift<=0; miso_bit<=0; frame_ok<=0;
   end else begin
    if(!sck[2] && sck[1]) begin
     rx_shift<=received;
     bit_count<=bit_count+1'b1;
     if(bit_count==7) begin
      pos<=pos+1'b1; next_tx<=0;
      if(pos<5 || (command==8'h20 && pos<5+length)) crc<=crc_byte(crc,received);
      case(pos)
       0:command<=received;
       1:address[7:0]<=received;
       2:address[15:8]<=received;
       3:length[7:0]<=received;
       4:begin
        length[15:8]<=received;
        if(command==8'h10 && received==0 && length[7:0]<=64) begin
         read_snapshot<=read_payload;
         next_tx<=read_payload[7:0];
        end
       end
       default:begin
        if(length>0 && length<=64) begin
         if(pos<5+length) begin
          if(command==8'h20) payload[pos-5]<=received;
          if(command==8'h10 && pos<4+length) next_tx<=read_snapshot[(pos-4)*8 +: 8];
         end else if(pos<9+length) begin
          case(pos-5-length)
           0:crc_received[7:0]<=received;
           1:crc_received[15:8]<=received;
           2:crc_received[23:16]<=received;
           3:begin
            frame_ok<=({received,crc_received[23:0]}==~crc) &&
             ((command==8'h10 && valid_read) || (command==8'h20 && valid_write));
            next_tx<=({received,crc_received[23:0]}==~crc) &&
             ((command==8'h10 && valid_read) || (command==8'h20 && valid_write)) ? 8'h79 : 8'h1f;
           end
          endcase
         end else if(pos==9+length && frame_ok) begin
          watchdog<=0;
          if(command==8'h20) begin
           case(address)
            16'h100:begin shadow_enable<=payload[0][0]; shadow_base<=payload[1]; shadow_amp<=payload[2];
             shadow_period<=new_period; shadow_alpha<=new_alpha; committed<=0; end
            16'h40:pending_generation<={payload[3],payload[2],payload[1],payload[0]};
            16'h10:case(payload[0])
             1:begin active_enable<=shadow_enable; active_base<=shadow_base; active_amp<=shadow_amp;
              active_period<=shadow_period; active_alpha<=shadow_alpha; generation<=pending_generation;
              committed<=1; link_error<=0; sample_index<=0; level<=0; end
             2:begin running<=1; sample_index<=0; level<=0; end
             4:begin running<=0; sample_index<=0; level<=0; link_error<=0; end
            endcase
           endcase
          end
         end
        end
       end
      endcase
     end
    end
    if(sck[2] && !sck[1]) begin
     if(bit_count==0) begin miso_bit<=next_tx[7]; tx_shift<={next_tx[6:0],1'b0}; end
     else begin miso_bit<=tx_shift[7]; tx_shift<={tx_shift[6:0],1'b0}; end
    end
   end
  end
 end
endmodule
