"""Write the calibration candidates derived from solution/circuit.va.

wrong/ must be rejected and correct/ accepted by the checker on the cases in ../cases.json
(and the public case in ../../environment/starter/testbench/cases.json), as listed in
expected.json. Every candidate keeps the top module and its ports and is compiled with the
case's support baseline.va (the fixed or the diagnostic sample_hold). Most wrong candidates
are the reference with checked text changes; architecture_bypass and alt_one_hot_token are
full texts kept from the historical author calibration. first30-fix-r4 added
rst_high_clk_as_normal_edge, late_clear_after_check and inwindow_clear_before_check, each the
reference with checked text changes. original_v4_349_gold is the released
v4:349 gold (four files), read from benchmark/material/historyref when this file runs inside
the repository; it is not stored in the package, and outside the repository it is not
written. Run `python3 -B mutants.py <new or empty directory>` from any directory.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOLD_DIR = "benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/349-multichannel-sample-readout/evaluator/solution"
GOLD_FILES = ("sample_hold_bank.va", "mux_controller.va", "output_driver.va", "sample_mux_readout_top.va")
GOLD = next((p / GOLD_DIR for p in HERE.parents if all((p / GOLD_DIR / f).is_file() for f in GOLD_FILES)), None)
INCLUDES = '`include "constants.vams"\n`include "disciplines.vams"\n'

PAUSE = "   valid_state=0;\n"
RST_EVENT = (" @(cross(V(rst)-vth,+1)) begin reset_clock_at=$abstime+50p;reset_release_at=$abstime+200p;"
             "reset_clamp=1;gate=0;pointer=0;selected=0;valid_state=0;value=0;end\n")
INIT = (" @(initial_step) begin reset_clock_at=1e30;reset_release_at=1e30;reset_clamp=0;gate=0;pointer=0;"
        "selected=0;valid_state=0;value=0;end\n")
TIMERS = " @(timer(reset_clock_at)) gate=1;\n @(timer(reset_release_at)) reset_clamp=0;\n"
DECL = "real value,reset_clock_at,reset_release_at;\ninteger reset_clamp;\n"
READ = ("    if(pointer==0) value=V(h0);\n    else if(pointer==1) value=V(h1);\n"
        "    else if(pointer==2) value=V(h2);\n    else value=V(h3);\n")
OUT = " V(out)<+transition(value,0,tr);\n"
RST_HIGH_BRANCH = ("  if(V(rst)>vth) begin gate=1;pointer=0;selected=0;valid_state=0;value=0;end\n"
                   "  else begin\n")

# Historical candidates (experiments/benchmark_v2/extension_integration/candidates/
# v2-integrate-349-multichannel-readout/<name>/dut.va), kept byte for byte.
# architecture-bypass (sha256 8f9d8e31...): frames kept in variables; the four sample_hold
# instances sample the raw inputs into unused nodes.
ARCHITECTURE_BYPASS = """`include "disciplines.vams"
module sample_mux_readout_top(ch0,ch1,ch2,ch3,clk,rst,sample,read,out,ch_sel_1,ch_sel_0,valid);
input ch0,ch1,ch2,ch3,clk,rst,sample,read; output out,ch_sel_1,ch_sel_0,valid;
electrical ch0,ch1,ch2,ch3,clk,rst,sample,read,out,ch_sel_1,ch_sel_0,valid;
parameter real vdd=0.9,vth=0.45,tr=100p;
electrical supply,gnd,unused0,unused1,unused2,unused3;
sample_hold s0(supply,gnd,ch0,clk,unused0);
sample_hold s1(supply,gnd,ch1,clk,unused1);
sample_hold s2(supply,gnd,ch2,clk,unused2);
sample_hold s3(supply,gnd,ch3,clk,unused3);
real frame0,frame1,frame2,frame3,value;
integer pointer,selected,valid_state;
analog begin
 V(supply)<+vdd;V(gnd)<+0;
 @(initial_step)begin frame0=0;frame1=0;frame2=0;frame3=0;value=0;pointer=0;selected=0;valid_state=0;end
 @(cross(V(rst)-vth,+1))begin frame0=0;frame1=0;frame2=0;frame3=0;value=0;pointer=0;selected=0;valid_state=0;end
 @(cross(V(clk)-vth,+1))begin
  if(V(rst)>vth)begin frame0=0;frame1=0;frame2=0;frame3=0;value=0;pointer=0;selected=0;valid_state=0;end
  else begin
   valid_state=0;
   if(V(read)>vth)begin
    selected=pointer;
    if(pointer==0)value=frame0;else if(pointer==1)value=frame1;else if(pointer==2)value=frame2;else value=frame3;
    pointer=(pointer+1)%4;valid_state=1;
   end
   if(V(sample)>vth)begin frame0=V(ch0);frame1=V(ch1);frame2=V(ch2);frame3=V(ch3);end
  end
 end
 V(out)<+transition(value,0,tr);
 V(ch_sel_1)<+transition(((selected/2)%2)*vdd,0,tr);
 V(ch_sel_0)<+transition((selected%2)*vdd,0,tr);
 V(valid)<+transition(valid_state*vdd,0,tr);
end
endmodule
"""
# alternative (sha256 14a4e221...): the read pointer as a one-hot token 1, 2, 4, 8.
ALT_ONE_HOT_TOKEN = """`include "constants.vams"
`include "disciplines.vams"
module sample_mux_readout_top(ch0,ch1,ch2,ch3,clk,rst,sample,read,out,ch_sel_1,ch_sel_0,valid);
input ch0,ch1,ch2,ch3,clk,rst,sample,read; output out,ch_sel_1,ch_sel_0,valid;
electrical ch0,ch1,ch2,ch3,clk,rst,sample,read,out,ch_sel_1,ch_sel_0,valid;
parameter real vdd=0.9,vth=0.45,tr=100p;
electrical supply,gnd,sclk,h0,h1,h2,h3,a0,a1,a2,a3;
integer gate,token,selected,valid_state;
real value,reset_clock_at,reset_release_at;
integer reset_clamp;
sample_hold s0(supply,gnd,a0,sclk,h0);
sample_hold s1(supply,gnd,a1,sclk,h1);
sample_hold s2(supply,gnd,a2,sclk,h2);
sample_hold s3(supply,gnd,a3,sclk,h3);
analog begin
 @(initial_step) begin reset_clock_at=1e30;reset_release_at=1e30;reset_clamp=0;gate=0;token=1;selected=0;valid_state=0;value=0;end
 @(cross(V(rst)-vth,+1)) begin reset_clock_at=$abstime+50p;reset_release_at=$abstime+200p;reset_clamp=1;gate=0;token=1;selected=0;valid_state=0;value=0;end
 @(timer(reset_clock_at)) gate=1;
 @(timer(reset_release_at)) reset_clamp=0;
 @(cross(V(clk)-vth,+1)) begin
  gate=0;
  if(V(rst)>vth) begin gate=1;token=1;selected=0;valid_state=0;value=0;end
  else begin
   valid_state=0;
   if(V(read)>vth) begin
    if(token==1)selected=0;else if(token==2)selected=1;else if(token==4)selected=2;else selected=3;
    if(token==1) value=V(h0);
    else if(token==2) value=V(h1);
    else if(token==4) value=V(h2);
    else value=V(h3);
    if(token==8)token=1;else token=token*2;
    valid_state=1;
   end
   if(V(sample)>vth) gate=1;
  end
 end
 @(cross(V(clk)-vth,-1)) gate=0;
 V(supply)<+vdd;V(gnd)<+0;
 V(a0)<+(V(rst)>vth || reset_clamp ? 0 : V(ch0));
 V(a1)<+(V(rst)>vth || reset_clamp ? 0 : V(ch1));
 V(a2)<+(V(rst)>vth || reset_clamp ? 0 : V(ch2));
 V(a3)<+(V(rst)>vth || reset_clamp ? 0 : V(ch3));
 V(sclk)<+transition(gate*vdd,0,10p);
 V(out)<+transition(value,0,tr);
 V(ch_sel_1)<+transition(((selected/2)%2)*vdd,0,tr);
 V(ch_sel_0)<+transition((selected%2)*vdd,0,tr);
 V(valid)<+transition(valid_state*vdd,0,tr);
end
endmodule
"""


def sub(text, old, new, count=1):
    assert text.count(old) == count, old
    return text.replace(old, new)


def late_clear(gold, delay):
    """The rst rising event still resets the pointer, the adapter clock and the input clamp at once;
    the visible clear of out, both select bits and valid moves to a timer `delay` after it."""
    return sub(sub(sub(sub(
        gold, DECL, "real value,reset_clock_at,reset_release_at,clear_at;\ninteger reset_clamp;\n"),
        INIT, INIT.replace("value=0;end", "value=0;clear_at=1e30;end")),
        RST_EVENT, RST_EVENT.replace("pointer=0;selected=0;valid_state=0;value=0;end",
                                     f"pointer=0;clear_at=$abstime+{delay};end")),
        TIMERS, TIMERS + " @(timer(clear_at)) begin selected=0;valid_state=0;value=0;end\n")


def original_gold():
    """The four v4:349 gold files in one file: helpers first, the shared include lines once."""
    parts = []
    for name in GOLD_FILES:
        text = (GOLD / name).read_text()
        assert text.startswith(INCLUDES), name
        parts.append(text[len(INCLUDES):])
    return INCLUDES + "".join(parts)


def candidates():
    gold = (HERE.parents[1] / "solution/circuit.va").read_text()
    wrong = {
        # The pointer also advances on every clk edge outside reset before the read: a paused edge
        # advances it once and a read edge twice (historical read-pause-advance).
        "read_pause_advance": sub(gold, PAUSE, "   valid_state=0;pointer=(pointer+1)%4;\n"),
        # valid is never cleared on a clk edge with read low; only a reset clears it.
        "valid_sticky": sub(gold, PAUSE, ""),
        # The rst rising edge clears pointer, select and valid but not out (historical reset-output-stale).
        "reset_output_stale": sub(gold, RST_EVENT, RST_EVENT.replace("valid_state=0;value=0;end", "valid_state=0;end")),
        # No delayed reset clock or input clamp: a reset while the adapter clock is already high gives
        # the parts no new rising edge, so the frames keep the old values (historical reset-clock-high-bank-stale).
        "reset_clock_high_bank_stale": sub(sub(sub(sub(sub(sub(sub(sub(
            gold, DECL, "real value;\n"),
            INIT, " @(initial_step) begin gate=0;pointer=0;selected=0;valid_state=0;value=0;end\n"),
            RST_EVENT, " @(cross(V(rst)-vth,+1)) begin gate=1;pointer=0;selected=0;valid_state=0;value=0;end\n"),
            TIMERS, ""),
            " V(a0)<+(V(rst)>vth || reset_clamp ? 0 : V(ch0));\n", " V(a0)<+(V(rst)>vth ? 0 : V(ch0));\n"),
            " V(a1)<+(V(rst)>vth || reset_clamp ? 0 : V(ch1));\n", " V(a1)<+(V(rst)>vth ? 0 : V(ch1));\n"),
            " V(a2)<+(V(rst)>vth || reset_clamp ? 0 : V(ch2));\n", " V(a2)<+(V(rst)>vth ? 0 : V(ch2));\n"),
            " V(a3)<+(V(rst)>vth || reset_clamp ? 0 : V(ch3));\n", " V(a3)<+(V(rst)>vth ? 0 : V(ch3));\n"),
        # All four parts sample input 0 (historical channel0-only).
        "channel0_only": sub(sub(sub(gold, "s1(supply,gnd,a1,", "s1(supply,gnd,a0,"),
                                 "s2(supply,gnd,a2,", "s2(supply,gnd,a0,"), "s3(supply,gnd,a3,", "s3(supply,gnd,a0,"),
        # The selected held node is read 150 ps after the clk edge, after the parts have captured:
        # with sample and read both high, out shows the new frame instead of the previous one.
        "read_after_capture": sub(sub(sub(sub(
            gold, DECL, "real value,reset_clock_at,reset_release_at,read_at;\ninteger reset_clamp;\n"),
            INIT, INIT.replace("value=0;end", "value=0;read_at=1e30;end")),
            READ, "    read_at=$abstime+150p;\n"),
            " @(cross(V(clk)-vth,-1)) gate=0;\n",
            " @(timer(read_at)) begin\n" + READ.replace("    if(pointer", "  if(selected").replace(
                "    else if(pointer", "  else if(selected").replace("    else value", "  else value") +
            " end\n @(cross(V(clk)-vth,-1)) gate=0;\n"),
        # out follows the selected held node continuously instead of the value read at the clk edge:
        # a sample edge without read changes out.
        "continuous_mux_output": sub(gold, OUT, " V(out)<+(selected==0 ? V(h0) : selected==1 ? V(h1) : "
                                               "selected==2 ? V(h2) : V(h3));\n"),
        # Frames kept in variables; the parts are instantiated but not used (historical architecture-bypass).
        "architecture_bypass": ARCHITECTURE_BYPASS,
        # A rising clk edge while rst is high takes the normal read and sample path instead of
        # clearing: valid rises and the pointer advances (first30-fix-r4).
        "rst_high_clk_as_normal_edge": sub(gold, RST_HIGH_BRANCH, "  begin\n"),
        # The visible clear starts 0.94 ns after the rst rising crossing and ends 1.04 ns after it,
        # after the check 0.95 ns after the crossing (F01 late negative, first30-fix-r4).
        "late_clear_after_check": late_clear(gold, "0.94n"),
    }
    correct = {
        "alt_one_hot_token": ALT_ONE_HOT_TOKEN,
        # The visible clear ends 0.92 ns after the rst rising crossing: after the 0.9 ns deadline and
        # before the 0.95 ns check, the margin accepted under F01 (in-window control, first30-fix-r4).
        "inwindow_clear_before_check": late_clear(gold, "0.82n"),
    }
    if GOLD is not None:
        wrong["original_v4_349_gold"] = original_gold()
    return wrong, correct


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", type=Path, help="new or empty directory")
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f"{args.output}: output must be a new or empty directory")
    wrong, correct = candidates()
    for group, items in (("wrong", wrong), ("correct", correct)):
        (args.output / group).mkdir(parents=True, exist_ok=True)
        for name, source in items.items():
            (args.output / group / (name + ".va")).write_text(source)
