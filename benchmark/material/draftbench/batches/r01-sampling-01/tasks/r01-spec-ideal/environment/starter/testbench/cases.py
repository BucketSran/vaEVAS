"""Exploratory public cases. Values are examples, not finalized domain limits."""
NS = 1e-9

def control(initial, changes, width=0.4, stop=60):
    points = [[0.0, initial]]
    level = initial
    for t, value in changes:
        points.extend([[(t-width/2)*NS, level], [(t+width/2)*NS, value]])
        level = value
    points.append([stop*NS, level])
    return points

def inst(name, track, rst, vin=None, vth=0.9, vinit=0.9):
    return dict(name=name, vth=vth, vinit=vinit,
                vin=vin or [[0, 0.2], [8*NS, 0.4], [16*NS, 1.6],
                            [30*NS, 0.2], [60*NS, 0.8]], track=track, rst=rst)

def public_cases():
    low, high = control(0, []), control(1.8, [])
    startup = [inst(f"t{t}r{r}", high if t else low, high if r else low,
                    vinit=0.35) for t in (0, 1) for r in (0, 1)]
    startup.extend([
        inst("equality", control(0.9, []), control(0.9, [])),
        inst("equality_track", control(0.9, []), low),
        inst("equality_reset", high, control(0.9, []))])
    return [
        dict(name="startup", stop=60*NS, instances=startup),
        dict(name="windows", stop=60*NS, instances=[inst("main",
             control(0, [(4,1.8),(20,0),(30,1.8),(42,0)]), low)]),
        dict(name="reset_history", stop=60*NS, instances=[
            inst("release_hold", control(0,[(2,1.8),(12,0),(38,1.8),(48,0)]),
                 control(0,[(17,1.8),(29,0)]), vinit=0.55),
            inst("release_track",control(0,[(2,1.8),(12,0),(23,1.8),(40,0)]),
                 control(0,[(17,1.8),(29,0)]), vinit=1.1),
            inst("close_in_reset",control(1.8,[(22,0),(38,1.8),(48,0)]),
                 control(0,[(17,1.8),(29,0)]), vinit=0.65)]),
        dict(name="isolation",stop=60*NS,instances=[
            inst("a",control(0,[(6,1.8),(24,0)]),low,vth=0.6,vinit=0.3),
            inst("b",control(1.8,[(24,0),(36,1.8),(50,0)]),
                 control(0,[(9,1.8),(19,0)]),vth=1.1,vinit=1.2,
                 vin=[[0,1.4],[20*NS,0.3],[60*NS,1.0]]),
            inst("c",control(0,[(6,1.8),(24,0)]),low,vth=0.6,vinit=0.7,
                 vin=[[0,1.5],[60*NS,0.1]])])]
