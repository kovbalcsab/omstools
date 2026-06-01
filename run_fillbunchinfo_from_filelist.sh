#!/bin/bash

set -euo pipefail

usage() {
  cat <<EOF
Usage: $0 --input <filelist.txt> [--output-dir filling_schemes] [--max-files N] [--runlist-out runlist.txt]

Options:
  --input <path>         Text file with one ROOT file path per line
  --output-dir <path>    Directory for per-run fillbunchinfo CSV files
  --max-files <N>        Optional limit passed to ExecuteExtractRunList
  --runlist-out <path>   Optional path to save the extracted unique run list
  --help                 Show this help message
EOF
}

abspath() {
  local path="$1"
  if [[ "$path" = /* ]]; then
    printf '%s\n' "$path"
  else
    printf '%s\n' "$PWD/$path"
  fi
}

INPUT_FILELIST=""
OUTPUT_DIR="filling_schemes"
MAX_FILES=""
RUNLIST_OUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --input)
      INPUT_FILELIST="$2"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --max-files)
      MAX_FILES="$2"
      shift 2
      ;;
    --runlist-out)
      RUNLIST_OUT="$2"
      shift 2
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$INPUT_FILELIST" ]]; then
  echo "error: --input is required" >&2
  usage >&2
  exit 1
fi

if [[ ! -f "$INPUT_FILELIST" ]]; then
  echo "error: input file list not found: $INPUT_FILELIST" >&2
  exit 1
fi

INPUT_FILELIST="$(abspath "$INPUT_FILELIST")"
OUTPUT_DIR="$(abspath "$OUTPUT_DIR")"
if [[ -n "$RUNLIST_OUT" ]]; then
  RUNLIST_OUT="$(abspath "$RUNLIST_OUT")"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -x ./ExecuteExtractRunList || ExtractRunList.cpp -nt ./ExecuteExtractRunList ]]; then
  echo "Compiling ExecuteExtractRunList..."
  g++ ExtractRunList.cpp -O3 -std=c++17 -o ExecuteExtractRunList `root-config --cflags --glibs`
fi

mkdir -p "$OUTPUT_DIR"
mkdir -p /tmp/bakovacs

TEMP_RUNLIST="$(mktemp /tmp/bakovacs/runlist_from_filelist.XXXXXX.txt)"
cleanup() {
  rm -f "$TEMP_RUNLIST"
}
trap cleanup EXIT

EXTRACT_ARGS=(--input "$INPUT_FILELIST" --output "$TEMP_RUNLIST")
if [[ -n "$MAX_FILES" ]]; then
  EXTRACT_ARGS+=(--max-files "$MAX_FILES")
fi

./ExecuteExtractRunList "${EXTRACT_ARGS[@]}"

if [[ -n "$RUNLIST_OUT" ]]; then
  mkdir -p "$(dirname "$RUNLIST_OUT")"
  cp "$TEMP_RUNLIST" "$RUNLIST_OUT"
fi

while IFS= read -r RUN; do
  [[ -z "$RUN" ]] && continue
  OUTPUT_FILE="$OUTPUT_DIR/fillbunchinfo_run${RUN}.csv"
  echo "Downloading fill bunch info for run $RUN -> $OUTPUT_FILE"
  python3 fillbunchinfo.py --run "$RUN" --outcsv "$OUTPUT_FILE"
done < "$TEMP_RUNLIST"

echo "Finished writing per-run filling scheme CSV files to $OUTPUT_DIR"
