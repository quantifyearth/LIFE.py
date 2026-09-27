#!/bin/sh
# Query a store and download a small region. Run: sh examples/cli.sh STORE [OUTPUT]
set -eu
store=${1:?Give a local Zarr store directory or URL}
output=${2:-region.npz}
life-metric query -19.5 47 "$store" --scenario arable --curve 0.25 --json
life-metric download "$output" "$store" --bbox 43 -26 51 -12 --taxon all
