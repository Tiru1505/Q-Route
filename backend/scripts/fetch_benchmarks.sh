#!/usr/bin/env bash
# Downloads open traffic-forecasting benchmarks from HuggingFace mirrors.
# (Zenodo blocks file downloads from some networks; HF mirrors are equivalent.)
set -u
B="data/raw/benchmarks"
HF="https://huggingface.co/datasets"
mkdir -p "$B/metr-la/sensor_graph" "$B/pems-bay/sensor_graph"

get () { # url dest
  if [ -s "$2" ]; then echo "  skip (exists): $2"; return; fi
  curl -sL --max-time 900 --retry 3 "$1" -o "$2" \
    -w "  %{http_code}  %{size_download} bytes  -> $2\n"
}

echo "== METR-LA (207 sensors, LA highways, 5-min, Mar-Jun 2012) =="
get "$HF/jimmygao3218/METRLA/resolve/main/metr-la.h5"                    "$B/metr-la/metr-la.h5"
get "$HF/jimmygao3218/METRLA/resolve/main/adj_mx.pkl"                    "$B/metr-la/adj_mx.pkl"
for f in sensor_locations.csv distances.csv adj_mx.npy adj_mx_mapping.json; do
  get "$HF/witgaw/METR-LA/resolve/main/sensor_graph/$f"                  "$B/metr-la/sensor_graph/$f"
done
for s in train val test; do
  get "$HF/witgaw/METR-LA/resolve/main/$s.parquet"                       "$B/metr-la/$s.parquet"
done

echo "== PEMS-BAY (325 sensors, Bay Area, 5-min, Jan-May 2017) =="
get "$HF/jimmygao3218/PEMSBAY/resolve/main/PEMS-BAY.h5"                  "$B/pems-bay/pems-bay.h5"
get "$HF/jimmygao3218/PEMSBAY/resolve/main/adj_mx_bay.pkl"               "$B/pems-bay/adj_mx_bay.pkl"
for f in sensor_locations.csv distances.csv adj_mx.npy adj_mx_mapping.json; do
  get "$HF/witgaw/PEMS-BAY/resolve/main/sensor_graph/$f"                 "$B/pems-bay/sensor_graph/$f"
done
for s in train val test; do
  get "$HF/witgaw/PEMS-BAY/resolve/main/$s.parquet"                      "$B/pems-bay/$s.parquet"
done
echo "== done =="
