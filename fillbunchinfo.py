import argparse
import csv
import sys

import util.oms as o
import util.utility as u

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = "Download bunch information for the fill corresponding to a run from OMS")
    parser.add_argument("--run", required = True, help = "one run number")
    parser.add_argument("--outcsv", required = False, help = "Optional csv output file")
    args = parser.parse_args()

    run = args.run

    runinfo, datas = o.get_bunch_info_by_run(run)
    if runinfo:
        runattr = runinfo["attributes"]
        print("Run summary: [\033[1;4m" + str(run) + "\033[0m]")
        if runattr.get("fill_number") is not None:
            print("    fill_number: \033[4m" + str(runattr["fill_number"]) + "\033[0m")

        fillinfo = o.get_fill_info(runattr["fill_number"]) if runattr.get("fill_number") is not None else None
        if fillinfo:
            fillattr = fillinfo["attributes"]
            for key in ["fill_type_party1", "fill_type_party2", "injection_scheme", "bunches_colliding"]:
                if key in fillattr and fillattr[key]:
                    print("    " + key + ": \033[4m" + str(fillattr[key]) + "\033[0m")

    print("Query resource: \033[4mbunches\033[0m")
    if not datas:
        print("\033[31merror: no bunch information found for run \"\033[4m" + str(run) + "\033[0m\033[31m\"\033[0m")
        sys.exit(1)

    fields = ["bunch_number", "peak_lumi", "intensity_beam_1", "intensity_beam_2", "pileup"]

    outputfile = u.setoutput(args.outcsv, "outcsv/fillbunchinfo.csv")
    with open(outputfile, "w", newline = "") as f:
        writer = csv.DictWriter(f, fieldnames = fields)
        writer.writeheader()
        for d in datas:
            writer.writerow({key : d["attributes"].get(key) for key in fields})

    print("Saved \033[4m" + str(len(datas)) + "\033[0m bunch rows.")
