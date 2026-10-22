`timescale 1ns/1ps
// Separate channel state; future MCU logic can drive mode_a/mode_b independently.
module wave_source_14 #(
    parameter integer SHAPE_ID = 0,
    parameter integer PERIOD_SAMPLES = 1000,
    parameter integer RAMP_STEP = 16,
    parameter integer INVERT_OUTPUT = 0
)(input wire sys_clk, input wire reset, input wire sample_enable,
  input wire [1:0] requested_mode, output reg [13:0] data);
reg [1:0] active_mode = 0;
reg [13:0] ramp = 0;
localparam [13:0] STEP = RAMP_STEP;
wire [14:0] next_ramp = {1'b0,ramp}+{1'b0,STEP};
reg [15:0] pulse_index = 0;
function [13:0] encode;
input [13:0] logical_code;
begin encode = INVERT_OUTPUT ? 14'd16383-logical_code : logical_code; end
endfunction
initial data = INVERT_OUTPUT ? 14'd8191 : 14'd8192;
function [13:0] pulse_code;
input [15:0] index;
begin
if (SHAPE_ID == 0) begin
case (index)
16'd0: pulse_code=14'd12288;
16'd1: pulse_code=14'd11961;
16'd2: pulse_code=14'd11659;
16'd3: pulse_code=14'd11382;
16'd4: pulse_code=14'd11127;
16'd5: pulse_code=14'd10892;
16'd6: pulse_code=14'd10676;
16'd7: pulse_code=14'd10478;
16'd8: pulse_code=14'd10295;
16'd9: pulse_code=14'd10127;
16'd10: pulse_code=14'd9972;
16'd11: pulse_code=14'd9830;
16'd12: pulse_code=14'd9699;
16'd13: pulse_code=14'd9578;
16'd14: pulse_code=14'd9468;
16'd15: pulse_code=14'd9366;
16'd16: pulse_code=14'd9272;
16'd17: pulse_code=14'd9185;
16'd18: pulse_code=14'd9106;
16'd19: pulse_code=14'd9033;
16'd20: pulse_code=14'd8966;
16'd21: pulse_code=14'd8904;
16'd22: pulse_code=14'd8847;
16'd23: pulse_code=14'd8795;
16'd24: pulse_code=14'd8746;
16'd25: pulse_code=14'd8702;
16'd26: pulse_code=14'd8661;
16'd27: pulse_code=14'd8624;
16'd28: pulse_code=14'd8589;
16'd29: pulse_code=14'd8557;
16'd30: pulse_code=14'd8528;
16'd31: pulse_code=14'd8501;
16'd32: pulse_code=14'd8477;
16'd33: pulse_code=14'd8454;
16'd34: pulse_code=14'd8433;
16'd35: pulse_code=14'd8414;
16'd36: pulse_code=14'd8396;
16'd37: pulse_code=14'd8380;
16'd38: pulse_code=14'd8365;
16'd39: pulse_code=14'd8351;
16'd40: pulse_code=14'd8338;
16'd41: pulse_code=14'd8326;
16'd42: pulse_code=14'd8316;
16'd43: pulse_code=14'd8306;
16'd44: pulse_code=14'd8297;
16'd45: pulse_code=14'd8288;
16'd46: pulse_code=14'd8281;
16'd47: pulse_code=14'd8274;
16'd48: pulse_code=14'd8267;
16'd49: pulse_code=14'd8261;
16'd50: pulse_code=14'd8256;
16'd51: pulse_code=14'd8250;
16'd52: pulse_code=14'd8246;
16'd53: pulse_code=14'd8241;
16'd54: pulse_code=14'd8238;
16'd55: pulse_code=14'd8234;
16'd56: pulse_code=14'd8231;
16'd57: pulse_code=14'd8227;
16'd58: pulse_code=14'd8225;
16'd59: pulse_code=14'd8222;
16'd60: pulse_code=14'd8220;
16'd61: pulse_code=14'd8217;
16'd62: pulse_code=14'd8215;
16'd63: pulse_code=14'd8213;
16'd64: pulse_code=14'd8212;
16'd65: pulse_code=14'd8210;
16'd66: pulse_code=14'd8209;
16'd67: pulse_code=14'd8207;
16'd68: pulse_code=14'd8206;
16'd69: pulse_code=14'd8205;
16'd70: pulse_code=14'd8204;
16'd71: pulse_code=14'd8203;
16'd72: pulse_code=14'd8202;
16'd73: pulse_code=14'd8201;
16'd74: pulse_code=14'd8201;
16'd75: pulse_code=14'd8200;
16'd76: pulse_code=14'd8199;
16'd77: pulse_code=14'd8199;
16'd78: pulse_code=14'd8198;
16'd79: pulse_code=14'd8198;
16'd80: pulse_code=14'd8197;
16'd81: pulse_code=14'd8197;
16'd82: pulse_code=14'd8196;
16'd83: pulse_code=14'd8196;
16'd84: pulse_code=14'd8196;
16'd85: pulse_code=14'd8195;
16'd86: pulse_code=14'd8195;
16'd87: pulse_code=14'd8195;
16'd88: pulse_code=14'd8195;
16'd89: pulse_code=14'd8194;
16'd90: pulse_code=14'd8194;
16'd91: pulse_code=14'd8194;
16'd92: pulse_code=14'd8194;
16'd93: pulse_code=14'd8194;
16'd94: pulse_code=14'd8194;
16'd95: pulse_code=14'd8193;
16'd96: pulse_code=14'd8193;
16'd97: pulse_code=14'd8193;
16'd98: pulse_code=14'd8193;
16'd99: pulse_code=14'd8193;
16'd100: pulse_code=14'd8193;
16'd101: pulse_code=14'd8193;
16'd102: pulse_code=14'd8193;
16'd103: pulse_code=14'd8193;
16'd104: pulse_code=14'd8193;
16'd105: pulse_code=14'd8193;
16'd106: pulse_code=14'd8193;
16'd107: pulse_code=14'd8193;
16'd108: pulse_code=14'd8193;
16'd109: pulse_code=14'd8192;
16'd110: pulse_code=14'd8192;
16'd111: pulse_code=14'd8192;
16'd112: pulse_code=14'd8192;
16'd113: pulse_code=14'd8192;
16'd114: pulse_code=14'd8192;
16'd115: pulse_code=14'd8192;
16'd116: pulse_code=14'd8192;
16'd117: pulse_code=14'd8192;
16'd118: pulse_code=14'd8192;
16'd119: pulse_code=14'd8192;
16'd120: pulse_code=14'd8192;
16'd121: pulse_code=14'd8192;
16'd122: pulse_code=14'd8192;
16'd123: pulse_code=14'd8192;
16'd124: pulse_code=14'd8192;
16'd125: pulse_code=14'd8192;
16'd126: pulse_code=14'd8192;
16'd127: pulse_code=14'd8192;
default: pulse_code=14'd8192;
endcase
end else begin
case (index)
16'd0: pulse_code=14'd11264;
16'd1: pulse_code=14'd11139;
16'd2: pulse_code=14'd11018;
16'd3: pulse_code=14'd10903;
16'd4: pulse_code=14'd10792;
16'd5: pulse_code=14'd10686;
16'd6: pulse_code=14'd10584;
16'd7: pulse_code=14'd10487;
16'd8: pulse_code=14'd10393;
16'd9: pulse_code=14'd10303;
16'd10: pulse_code=14'd10217;
16'd11: pulse_code=14'd10135;
16'd12: pulse_code=14'd10055;
16'd13: pulse_code=14'd9979;
16'd14: pulse_code=14'd9906;
16'd15: pulse_code=14'd9836;
16'd16: pulse_code=14'd9769;
16'd17: pulse_code=14'd9705;
16'd18: pulse_code=14'd9643;
16'd19: pulse_code=14'd9584;
16'd20: pulse_code=14'd9527;
16'd21: pulse_code=14'd9473;
16'd22: pulse_code=14'd9420;
16'd23: pulse_code=14'd9370;
16'd24: pulse_code=14'd9322;
16'd25: pulse_code=14'd9276;
16'd26: pulse_code=14'd9232;
16'd27: pulse_code=14'd9189;
16'd28: pulse_code=14'd9149;
16'd29: pulse_code=14'd9110;
16'd30: pulse_code=14'd9072;
16'd31: pulse_code=14'd9036;
16'd32: pulse_code=14'd9002;
16'd33: pulse_code=14'd8969;
16'd34: pulse_code=14'd8937;
16'd35: pulse_code=14'd8907;
16'd36: pulse_code=14'd8877;
16'd37: pulse_code=14'd8849;
16'd38: pulse_code=14'd8823;
16'd39: pulse_code=14'd8797;
16'd40: pulse_code=14'd8772;
16'd41: pulse_code=14'd8749;
16'd42: pulse_code=14'd8726;
16'd43: pulse_code=14'd8704;
16'd44: pulse_code=14'd8683;
16'd45: pulse_code=14'd8663;
16'd46: pulse_code=14'd8644;
16'd47: pulse_code=14'd8625;
16'd48: pulse_code=14'd8608;
16'd49: pulse_code=14'd8591;
16'd50: pulse_code=14'd8575;
16'd51: pulse_code=14'd8559;
16'd52: pulse_code=14'd8544;
16'd53: pulse_code=14'd8530;
16'd54: pulse_code=14'd8516;
16'd55: pulse_code=14'd8503;
16'd56: pulse_code=14'd8490;
16'd57: pulse_code=14'd8478;
16'd58: pulse_code=14'd8466;
16'd59: pulse_code=14'd8455;
16'd60: pulse_code=14'd8444;
16'd61: pulse_code=14'd8434;
16'd62: pulse_code=14'd8424;
16'd63: pulse_code=14'd8415;
16'd64: pulse_code=14'd8405;
16'd65: pulse_code=14'd8397;
16'd66: pulse_code=14'd8388;
16'd67: pulse_code=14'd8380;
16'd68: pulse_code=14'd8373;
16'd69: pulse_code=14'd8365;
16'd70: pulse_code=14'd8358;
16'd71: pulse_code=14'd8351;
16'd72: pulse_code=14'd8345;
16'd73: pulse_code=14'd8339;
16'd74: pulse_code=14'd8333;
16'd75: pulse_code=14'd8327;
16'd76: pulse_code=14'd8321;
16'd77: pulse_code=14'd8316;
16'd78: pulse_code=14'd8311;
16'd79: pulse_code=14'd8306;
16'd80: pulse_code=14'd8302;
16'd81: pulse_code=14'd8297;
16'd82: pulse_code=14'd8293;
16'd83: pulse_code=14'd8289;
16'd84: pulse_code=14'd8285;
16'd85: pulse_code=14'd8281;
16'd86: pulse_code=14'd8277;
16'd87: pulse_code=14'd8274;
16'd88: pulse_code=14'd8271;
16'd89: pulse_code=14'd8267;
16'd90: pulse_code=14'd8264;
16'd91: pulse_code=14'd8261;
16'd92: pulse_code=14'd8258;
16'd93: pulse_code=14'd8256;
16'd94: pulse_code=14'd8253;
16'd95: pulse_code=14'd8251;
16'd96: pulse_code=14'd8248;
16'd97: pulse_code=14'd8246;
16'd98: pulse_code=14'd8244;
16'd99: pulse_code=14'd8242;
16'd100: pulse_code=14'd8240;
16'd101: pulse_code=14'd8238;
16'd102: pulse_code=14'd8236;
16'd103: pulse_code=14'd8234;
16'd104: pulse_code=14'd8232;
16'd105: pulse_code=14'd8231;
16'd106: pulse_code=14'd8229;
16'd107: pulse_code=14'd8228;
16'd108: pulse_code=14'd8226;
16'd109: pulse_code=14'd8225;
16'd110: pulse_code=14'd8223;
16'd111: pulse_code=14'd8222;
16'd112: pulse_code=14'd8221;
16'd113: pulse_code=14'd8220;
16'd114: pulse_code=14'd8219;
16'd115: pulse_code=14'd8217;
16'd116: pulse_code=14'd8216;
16'd117: pulse_code=14'd8215;
16'd118: pulse_code=14'd8214;
16'd119: pulse_code=14'd8214;
16'd120: pulse_code=14'd8213;
16'd121: pulse_code=14'd8212;
16'd122: pulse_code=14'd8211;
16'd123: pulse_code=14'd8210;
16'd124: pulse_code=14'd8210;
16'd125: pulse_code=14'd8209;
16'd126: pulse_code=14'd8208;
16'd127: pulse_code=14'd8207;
default: pulse_code=14'd8192;
endcase
end
end
endfunction
always @(posedge sys_clk) begin
    if (reset) begin
        data <= encode(14'd8192); active_mode <= 0; ramp <= 0; pulse_index <= 0;
    end else if (sample_enable) begin
        if (requested_mode != active_mode) begin
            active_mode <= requested_mode;
            ramp <= STEP; pulse_index <= 1;
            case (requested_mode)
                1: data <= encode(0);
                2: data <= encode(pulse_code(0));
                default: data <= encode(14'd8192);
            endcase
        end else begin
            case (active_mode)
                1: begin data <= encode(ramp); ramp <= next_ramp[13:0]; end
                2: begin
                    data <= encode(pulse_code(pulse_index));
                    if (pulse_index == PERIOD_SAMPLES-1) pulse_index <= 0;
                    else pulse_index <= pulse_index+1'b1;
                end
                default: data <= encode(14'd8192);
            endcase
        end
    end
end
endmodule
