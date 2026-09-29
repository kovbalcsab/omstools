import argparse
import json
import re
import sys


def parse_args():
    parser = argparse.ArgumentParser(
        description="List exact HLT path names matching a pattern across certified runs in a JSON file"
    )
    parser.add_argument(
        "--json",
        required=True,
        help="Certification JSON file with run -> lumisection map",
    )
    parser.add_argument(
        "--pattern",
        required=True,
        help="Regex pattern matched against HLT path names",
    )
    parser.add_argument(
        "--literal",
        action="store_true",
        help="Treat --pattern as a literal string instead of a regex",
    )
    parser.add_argument(
        "--ignore-case",
        action="store_true",
        help="Ignore case when matching path names",
    )
    parser.add_argument(
        "--show-menus",
        action="store_true",
        help="Also print the HLT menu keys seen in each contiguous run segment",
    )
    return parser.parse_args()


def load_runs(json_path):
    with open(json_path) as handle:
        payload = json.load(handle)

    runs = sorted(int(run) for run in payload.keys())
    if not runs:
        raise ValueError(f'no runs found in "{json_path}"')
    return runs


def compile_matcher(pattern, literal=False, ignore_case=False):
    flags = re.IGNORECASE if ignore_case else 0
    source = re.escape(pattern) if literal else pattern
    return re.compile(source, flags)


def get_run_matches(run, matcher, oms_module):
    run_str = str(run)
    run_info = oms_module.get_run_info(run_str, verbose=False)
    if run_info is None:
        return None, []

    hlt_key = run_info["attributes"].get("hlt_key")
    paths = oms_module.get_hltlist_by_run(run_str)
    matches = sorted(path for path in paths if matcher.search(path))
    return hlt_key, matches


def build_segments(run_summaries):
    segments = []
    if not run_summaries:
        return segments

    start_run, start_menu, start_paths = run_summaries[0]
    current_paths = tuple(start_paths)
    current_menus = {start_menu} if start_menu else set()
    previous_run = start_run

    for run, menu, paths in run_summaries[1:]:
        path_tuple = tuple(paths)
        if path_tuple != current_paths:
            segments.append((start_run, previous_run, list(current_paths), sorted(current_menus)))
            start_run = run
            current_paths = path_tuple
            current_menus = set()
        if menu:
            current_menus.add(menu)
        previous_run = run

    segments.append((start_run, previous_run, list(current_paths), sorted(current_menus)))
    return segments


def print_summary(runs, pattern, segments, show_menus=False):
    print(f"Certified runs: {len(runs)} ({runs[0]}-{runs[-1]})")
    print(f"Pattern: {pattern}")
    print(f"Unique matched path sets: {len(segments)}")
    print()

    for start_run, end_run, paths, menus in segments:
        print(f"{start_run}-{end_run}")
        if show_menus:
            if menus:
                print("  HLT menus:")
                for menu in menus:
                    print(f"    {menu}")
            else:
                print("  HLT menus: none")

        if paths:
            for path in paths:
                print(f"  {path}")
        else:
            print("  No matching paths")
        print()


def main():
    args = parse_args()

    try:
        matcher = compile_matcher(args.pattern, literal=args.literal, ignore_case=args.ignore_case)
        runs = load_runs(args.json)
    except (OSError, ValueError, re.error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    import util.oms as oms

    run_summaries = []
    for run in runs:
        hlt_key, matches = get_run_matches(run, matcher, oms)
        run_summaries.append((run, hlt_key, matches))

    segments = build_segments(run_summaries)
    print_summary(runs, args.pattern, segments, show_menus=args.show_menus)


if __name__ == "__main__":
    main()
