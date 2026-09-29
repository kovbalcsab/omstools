import argparse
from collections import defaultdict
from datetime import datetime

import util.oms as o
import util.utility as u

def parse_oms_time(ts):
    if ts is None:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

# Classifies each lumisection's instantaneous luminosity trend as "leveled"
# (roughly flat, e.g. during beta*/crossing-angle leveling) or "decaying"
# (falling off, typically after leveling is exhausted), by fitting a local
# linear trend to avg_lumi vs. time over a window of neighboring lumisections
# and normalizing the slope by avg_lumi (relative slope, in s^-1).
#
# Defaults (window = 20 LS on each side, cutoff = 2e-5 s^-1) were picked by
# scanning a PbPb 2025 fill (11366 / run 400243, HIRun2025A): no active
# beta*/crossing-angle leveling, ~1h near-flat plateau after the peak, then a
# fast decay (~5-9e-5 s^-1 relative slope) over the ~8h fill. This combination
# correctly flagged the decay tail 100% of the time and the plateau ~85% of
# the time. Long, actively-leveled pp fills decay much more slowly (~1e-5
# s^-1, over 1-2 days) and need a larger window/smaller cutoff (e.g. ~100 LS,
# 5e-6) to resolve well -- pass --slope-window/--slope-cutoff to override for
# that case.
def lumi_trend_by_ls(byls, window = 20, cutoff = 2e-5):
    entries = []
    for ls, attr in byls.items():
        if attr["init_lumi"] is None or attr["end_lumi"] is None:
            continue
        avg_lumi = (attr["init_lumi"] + attr["end_lumi"]) / 2.
        if avg_lumi <= 0:
            continue
        t = parse_oms_time(attr["start_time"])
        if t is None:
            continue
        entries.append((ls, t.timestamp(), avg_lumi))
    entries.sort(key = lambda e: e[0])

    trend = {}
    n = len(entries)
    for i in range(n):
        ls_i, t_i, y_i = entries[i]
        pts = entries[max(0, i - window):min(n, i + window + 1)]
        if len(pts) < 2:
            trend[ls_i] = None
            continue
        tbar = sum(p[1] for p in pts) / len(pts)
        ybar = sum(p[2] for p in pts) / len(pts)
        num = sum((p[1] - tbar) * (p[2] - ybar) for p in pts)
        den = sum((p[1] - tbar) ** 2 for p in pts)
        if den == 0:
            trend[ls_i] = None
            continue
        rel_slope = (num / den) / y_i
        if rel_slope > cutoff:
            trend[ls_i] = "ramping"
        elif rel_slope < -cutoff:
            trend[ls_i] = "decaying"
        else:
            trend[ls_i] = "leveled"
    return trend

def read_runlumi_list(path):
    runlumis = defaultdict(set)
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            run, ls = int(parts[0]), int(parts[1])
            runlumis[run].add(ls)
    return runlumis

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Instantaneous luminosity for run-lumisection pairs listed in a text file')
    parser.add_argument('--inputtxt', required = True, help = 'Text file with "run lumi" pairs, one per line (e.g. output of runlumi_list.exe)')
    parser.add_argument('--outcsv', required = False, help = 'Optional csv output file')
    parser.add_argument('--slope-window', type = int, default = 20, help = 'Number of neighboring lumisections (on each side) used to fit the local avg_lumi trend (default: 20, i.e. ~16 min; tuned for PbPb fills -- use ~100 for long pp fills)')
    parser.add_argument('--slope-cutoff', type = float, default = 2e-5, help = 'Relative slope threshold in s^-1 below which a lumisection is classified "leveled" rather than "decaying"/"ramping" (default: 2e-5; tuned for PbPb fills -- use ~5e-6 for long pp fills)')
    args = parser.parse_args()

    runlumis = read_runlumi_list(args.inputtxt)
    npairs = sum(len(lss) for lss in runlumis.values())
    print("\033[2m" + str(len(runlumis)) + " runs, " + str(npairs) + " run-lumi pairs requested.\033[0m")

    outputfile = u.setoutput(args.outcsv, 'outcsv/instlumi.csv')
    nfound = 0
    with open(outputfile, 'w') as f:
        # units (from OMS lumisections meta): init_lumi/end_lumi/avg_lumi in 10^33 cm^-2 s^-1 (instantaneous),
        # delivered_lumi/recorded_lumi in pb^-1 (integrated over the lumisection)
        print("run, ls, init_lumi, end_lumi, avg_lumi, delivered_lumi, recorded_lumi, beams_stable, lumi_trend", file = f)
        for run in sorted(runlumis):
            print("\033[2mGetting lumisections for run " + str(run) + "...\033[0m")
            lumisections = o.get_by_range("run_number", run, run, "lumisections", per_page = 100)
            byls = { d["attributes"]["lumisection_number"] : d["attributes"] for d in lumisections }
            trend = lumi_trend_by_ls(byls, window = args.slope_window, cutoff = args.slope_cutoff)
            for ls in sorted(runlumis[run]):
                attr = byls.get(ls)
                if attr is None:
                    print("\033[31mwarning: run " + str(run) + ", ls " + str(ls) + " not found in OMS, skip.\033[0m")
                    continue
                avg_lumi = None
                if attr["init_lumi"] is not None and attr["end_lumi"] is not None:
                    avg_lumi = (attr["init_lumi"] + attr["end_lumi"]) / 2.
                print("{}, {}, {}, {}, {}, {}, {}, {}, {}".format(
                    run, ls,
                    u.mystr(attr["init_lumi"]), u.mystr(attr["end_lumi"]), u.mystr(avg_lumi),
                    u.mystr(attr["delivered_lumi"]), u.mystr(attr["recorded_lumi"]),
                    u.mystr(attr["beams_stable"]), u.mystr(trend.get(ls))), file = f)
                nfound = nfound + 1

    print("\n\033[2m" + str(nfound) + "/" + str(npairs) + " run-lumi pairs found.\033[0m")
