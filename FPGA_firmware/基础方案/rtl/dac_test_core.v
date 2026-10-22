`timescale 1ns/1ps
// All registers use the 50 MHz board clock. No fabric-generated internal clock.
module dac_test_core #(
    parameter integer CLOCK_DIV = 50,
    parameter integer PULSE_PERIOD = 1000
)(input wire sys_clk, input wire reset, input wire [1:0] requested_mode,
  output reg [7:0] dac_data, output reg dac_clk);
initial begin dac_data = 8'd128; dac_clk = 1'b0; end
reg [15:0] phase = 0;
reg [1:0] active_mode = 0;
reg [7:0] ramp = 0;
reg [15:0] pulse_index = 0;
function [7:0] pulse_code;
input [15:0] index;
begin
case (index)
16'd0: pulse_code = 8'd240;
16'd1: pulse_code = 8'd222;
16'd2: pulse_code = 8'd206;
16'd3: pulse_code = 8'd190;
16'd4: pulse_code = 8'd177;
16'd5: pulse_code = 8'd164;
16'd6: pulse_code = 8'd152;
16'd7: pulse_code = 8'd141;
16'd8: pulse_code = 8'd131;
16'd9: pulse_code = 8'd122;
16'd10: pulse_code = 8'd113;
16'd11: pulse_code = 8'd106;
16'd12: pulse_code = 8'd98;
16'd13: pulse_code = 8'd92;
16'd14: pulse_code = 8'd86;
16'd15: pulse_code = 8'd80;
16'd16: pulse_code = 8'd75;
16'd17: pulse_code = 8'd70;
16'd18: pulse_code = 8'd66;
16'd19: pulse_code = 8'd62;
16'd20: pulse_code = 8'd58;
16'd21: pulse_code = 8'd55;
16'd22: pulse_code = 8'd52;
16'd23: pulse_code = 8'd49;
16'd24: pulse_code = 8'd46;
16'd25: pulse_code = 8'd44;
16'd26: pulse_code = 8'd42;
16'd27: pulse_code = 8'd40;
16'd28: pulse_code = 8'd38;
16'd29: pulse_code = 8'd36;
16'd30: pulse_code = 8'd34;
16'd31: pulse_code = 8'd33;
16'd32: pulse_code = 8'd32;
16'd33: pulse_code = 8'd30;
16'd34: pulse_code = 8'd29;
16'd35: pulse_code = 8'd28;
16'd36: pulse_code = 8'd27;
16'd37: pulse_code = 8'd26;
16'd38: pulse_code = 8'd25;
16'd39: pulse_code = 8'd25;
16'd40: pulse_code = 8'd24;
16'd41: pulse_code = 8'd23;
16'd42: pulse_code = 8'd23;
16'd43: pulse_code = 8'd22;
16'd44: pulse_code = 8'd22;
16'd45: pulse_code = 8'd21;
16'd46: pulse_code = 8'd21;
16'd47: pulse_code = 8'd20;
16'd48: pulse_code = 8'd20;
16'd49: pulse_code = 8'd20;
16'd50: pulse_code = 8'd19;
16'd51: pulse_code = 8'd19;
16'd52: pulse_code = 8'd19;
16'd53: pulse_code = 8'd19;
16'd54: pulse_code = 8'd18;
16'd55: pulse_code = 8'd18;
16'd56: pulse_code = 8'd18;
16'd57: pulse_code = 8'd18;
16'd58: pulse_code = 8'd18;
16'd59: pulse_code = 8'd18;
16'd60: pulse_code = 8'd18;
16'd61: pulse_code = 8'd17;
16'd62: pulse_code = 8'd17;
16'd63: pulse_code = 8'd17;
default: pulse_code = 8'd16;
endcase
end
endfunction
always @(posedge sys_clk) begin
    if (reset) begin
        phase <= 0; dac_clk <= 0; dac_data <= 128;
        active_mode <= 0; ramp <= 0; pulse_index <= 0;
    end else begin
        if (phase == CLOCK_DIV-1) phase <= 0;
        else phase <= phase + 1'b1;
        // Change data on falling edge; rising edge follows half a sample later.
        if (phase == 0) begin
            dac_clk <= 0;
            if (requested_mode != active_mode) begin
                active_mode <= requested_mode;
                ramp <= 1; pulse_index <= 1;
                case (requested_mode)
                    1: dac_data <= 0;
                    2: dac_data <= pulse_code(0);
                    default: dac_data <= 128;
                endcase
            end else begin
                case (active_mode)
                    1: begin dac_data <= ramp; ramp <= ramp + 1'b1; end
                    2: begin
                        dac_data <= pulse_code(pulse_index);
                        if (pulse_index == PULSE_PERIOD-1) pulse_index <= 0;
                        else pulse_index <= pulse_index + 1'b1;
                    end
                    default: dac_data <= 128;
                endcase
            end
        end
        if (phase == CLOCK_DIV/2) dac_clk <= 1;
    end
end
endmodule
