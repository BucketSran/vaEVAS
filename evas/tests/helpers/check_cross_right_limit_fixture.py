"""Check the source-order right-limit fixture against the public frontend.

The VA bodies below are the working source. The programs in the JSON are a
derived snapshot read by the kernel unit tests (procedure_right_limit_tests).
The default run compares them in memory and does not write; --write rewrites
the snapshot explicitly.
"""
import hashlib
import json
import sys
from pathlib import Path

EVAS = Path(__file__).resolve().parents[2]
FIXTURE = EVAS / "rust_core/tests/fixtures/ir33_cross_right_limit.json"
BODIES = {
    "guard": ("u,y,r", "input u; output y; inout r;",
              "@(initial_step) begin q=0; p=0; end "
              "@(cross(V(u,r)-0.5,0)) begin if (V(u,r)>0.5) q=2; else q=3; end V(y,r)<+q;"),
    "unfired": ("u,w,y,r", "input u,w; output y; inout r;",
                "@(initial_step) begin q=0; p=0; end "
                "@(cross(V(u,r)-0.5,0)) begin if (V(w,r)>0.5) q=2; else q=3; end V(y,r)<+q;"),
    "arms": ("u,y,r", "input u; output y; inout r;",
             "@(initial_step) begin q=0; p=0; end "
             "@(cross(V(u,r)-0.5,0)) begin if (V(u,r)>0.5) q=2; else q=2; end V(y,r)<+q;"),
}


def snapshot():
    sys.path.insert(0, str(EVAS / "src"))
    from evas import Instance, compile_sources

    cases = {}
    for name, (ports, directions, body) in BODIES.items():
        text = (f'`include "disciplines.vams"\nmodule m({ports}); {directions} electrical {ports}; '
                f"real q, p; analog begin {body} end endmodule")
        connections = {port: ("0" if port == "r" else port) for port in ports.split(",")}
        program = compile_sources({"right.va": text}, [Instance("dut", "m", connections, {})])
        driven = [port for port in ports.split(",") if port in ("u", "w")]
        cases[name] = dict(program=json.loads(json.dumps(program.to_dict())), driven=driven)
    return json.dumps(dict(cases=cases), indent=1, sort_keys=True) + "\n"


def main():
    text = snapshot()
    if "--write" in sys.argv[1:]:
        FIXTURE.write_text(text)
    elif FIXTURE.read_text() != text:
        raise SystemExit("cross right-limit fixture differs from the current public frontend")
    print(json.dumps({
        "programs_match_frontend": True,
        "fixture_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "compiler_sha256": hashlib.sha256((EVAS / "src/evas/frontend.py").read_bytes()).hexdigest(),
    }))


if __name__ == "__main__":
    main()
