"""Generate matched N4 RTL fixtures from the integer reference; no hardware access."""
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pc_app/src"))
from nucsignal_app.bench import BenchConfig
from nucsignal_app.nuclear import reference


def main():
    folder = ROOT / "FPGA_firmware/基础方案/核信号单通道_V4/tb"
    cases = [
        (BenchConfig(96,84,20,2,nuclear=True,competition=True),2000),
        (BenchConfig(96,84,10,1,nuclear=True,competition=True),2000),
        (BenchConfig(96,84,1000,144.27,nuclear=True,competition=True),3000),
    ]
    for rms in (0,1,5,20):
        cases.append((BenchConfig(128,0,1000,12,nuclear=True,competition=True,
                                 noise_mode="gaussian",noise_rms_percent=rms),6000))
    cases.append((BenchConfig(96,84,128,145,nuclear=True,competition=True,random_events=True,
                             noise_mode="gaussian",noise_rms_percent=20,seed=17),6000))
    values, meta, calls = [], [], []
    import math
    for i,(config,size) in enumerate(cases):
        codes, events, _, clips = reference(config,size)
        start = len(values); values.extend(codes)
        alpha = math.floor(math.exp(-1/config.tau_us)*65536+.5)
        flags = int(config.noise_mode=="gaussian") | (int(config.allow_pileup)<<1)
        call = f"run_case({i+1},{config.baseline_code},{config.amplitude_code},{config.period_us},{alpha},{int(config.random_events)},{config.noise_rms_percent if config.noise_mode=='gaussian' else config.noise_peak_codes},{flags},{config.seed},{start},{size},{len(events)},{clips});"
        calls.append(call)
        d=asdict(config); d.pop("spectrum_table")
        meta.append({"config":d,"samples":size,"events":len(events),"clips":clips})
    (folder/"competition_expected.hex").write_text(''.join(f'{int(v):02x}\n' for v in values),encoding="ascii")
    (folder/"competition_expected.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    template=(folder/"tb_nuclear.sv").read_text(encoding="utf-8")
    prefix=template[:template.index(' reg [7:0] expected')].replace('module tb_nuclear;','module tb_competition;')
    body = '''
 reg [7:0] expected[0:__LAST__];
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
__CALLS__
  // Gaussian RMS outside 0..20 is rejected without changing shadow registers.
  tx[0]=0;tx[1]=21;tx[2]=0;tx[3]=1;tx[4]=0;tx[5]=0;tx[6]=0;tx[7]=2;
  tx[8]=1;tx[9]=0;tx[10]=0;tx[11]=0;
  transaction(8'h20,16'h110,12);check(ack==8'h1f,"reject Gaussian RMS21");
  key_stop_n=0;#1000;check(!dut.running && data==16,"N4 local reset");
  $display("PASS: competition V4 %0d checks; DAC clocks %0d",checks,clock_checks);$finish;
 end
endmodule
'''
    body=body.replace('__LAST__',str(len(values)-1)).replace('__CALLS__','\n'.join('  '+c for c in calls))
    (folder/"tb_competition.sv").write_text(prefix+body,encoding="utf-8")
    print(f"Generated {len(cases)} cases, {len(values)} DAC samples")


if __name__ == '__main__':
    main()
