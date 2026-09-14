"""
Phase 1 -- dataset-first inspection.

Reads config/datasets.yaml, inspects whatever is actually on disk, and writes one
report per dataset to results/dataset_reports/. Nothing here trains anything; the
point is to establish what each source genuinely contains BEFORE any modelling
decision is made.

    python scripts/inspect_datasets.py

Every inspector reports the same contract:
    shape / columns / dtypes / missing / duplicates / temporal / geographic /
    class distribution (vision) -- then a verdict on what the dataset can and
    cannot support.
"""
import json
import os
import re
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "results" / "dataset_reports"

# IDD level-1 (coarse) label ids. IDD Lite ships ONLY these 7 + 255=ignore.
IDD_LITE_CLASSES = {
    0: "drivable", 1: "non-drivable", 2: "living things", 3: "vehicles",
    4: "road-side objects", 5: "far objects", 6: "sky", 255: "ignore/unlabelled",
}


def resolve(path_str):
    return Path(os.path.expanduser(str(path_str)))


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return "%.1f %s" % (n, unit)
        n /= 1024
    return "%.1f TB" % n


def dir_size(path):
    if path.is_file():
        return path.stat().st_size
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


# --------------------------------------------------------------------------- #
# generic tabular contract (§18 items 2-9)
# --------------------------------------------------------------------------- #
def profile_frame(df, name):
    out = {"name": name, "rows": int(len(df)), "cols": int(df.shape[1])}
    out["columns"] = [
        {
            "name": str(c),
            "dtype": str(df[c].dtype),
            "missing": int(df[c].isna().sum()),
            "missing_pct": round(float(df[c].isna().mean() * 100), 2),
            "unique": int(df[c].nunique(dropna=True)),
        }
        for c in df.columns
    ]
    out["duplicate_rows"] = int(df.duplicated().sum())

    # temporal structure -- decides LSTM/GRU viability
    tcols = [c for c in df.columns
             if pd.api.types.is_datetime64_any_dtype(df[c])
             or re.search(r"time|date|stamp", str(c), re.I)]
    out["temporal"] = None
    for c in tcols:
        try:
            ts = pd.to_datetime(df[c], errors="coerce").dropna()
        except Exception:
            continue
        if len(ts) < 2:
            continue
        gaps = ts.sort_values().diff().dropna()
        out["temporal"] = {
            "column": str(c),
            "start": str(ts.min()), "end": str(ts.max()),
            "span_days": round((ts.max() - ts.min()).total_seconds() / 86400, 2),
            "n_timestamps": int(ts.nunique()),
            "median_gap_s": float(gaps.median().total_seconds()) if len(gaps) else None,
            "regular": bool(gaps.nunique() <= 3) if len(gaps) else False,
        }
        break

    # geographic structure
    latc = [c for c in df.columns if re.fullmatch(r"lat|latitude|y", str(c), re.I)]
    lonc = [c for c in df.columns if re.fullmatch(r"lon|lng|longitude|x", str(c), re.I)]
    out["geographic"] = None
    if latc and lonc:
        out["geographic"] = {
            "lat_col": latc[0], "lon_col": lonc[0],
            "bbox": [float(df[lonc[0]].min()), float(df[latc[0]].min()),
                     float(df[lonc[0]].max()), float(df[latc[0]].max())],
        }
    return out


def inspect_tabular(path):
    frames = []
    files = sorted([p for p in (path.rglob("*") if path.is_dir() else [path])
                    if p.suffix.lower() in (".csv", ".xlsx", ".xls", ".parquet")])
    for f in files:
        try:
            if f.suffix.lower() == ".parquet":
                sheets = {f.stem: pd.read_parquet(f)}
            elif f.suffix.lower() == ".csv":
                sheets = {f.stem: pd.read_csv(f)}
            else:
                xl = pd.ExcelFile(f)
                sheets = {s: xl.parse(s) for s in xl.sheet_names}
        except Exception as exc:
            frames.append({"name": f.name, "error": str(exc)})
            continue
        for sheet, df in sheets.items():
            if df.empty:
                continue
            frames.append(profile_frame(df, "%s::%s" % (f.name, sheet)))
    return {"kind": "tabular", "n_files": len(files), "frames": frames}


def inspect_timeseries(path):
    """HDF5 speed matrices (METR-LA / PEMS-BAY): timesteps x sensors."""
    df = pd.read_hdf(path)
    vals = df.to_numpy(dtype="float64")
    gaps = pd.Series(df.index).diff().dropna()
    sensors = path.parent / "sensor_graph/sensor_locations.csv"
    geo = None
    if sensors.exists():
        s = pd.read_csv(sensors)
        geo = {"n_sensors": int(len(s)),
               "bbox": [float(s.iloc[:, 2].min()), float(s.iloc[:, 1].min()),
                        float(s.iloc[:, 2].max()), float(s.iloc[:, 1].max())]}
    return {
        "kind": "timeseries",
        "timesteps": int(df.shape[0]), "sensors": int(df.shape[1]),
        "start": str(df.index[0]), "end": str(df.index[-1]),
        "step_s": float(gaps.mode().iloc[0].total_seconds()),
        "regular": bool(gaps.nunique() == 1),
        "value_min": float(np.nanmin(vals)), "value_mean": float(np.nanmean(vals)),
        "value_max": float(np.nanmax(vals)),
        "zero_pct": round(float((vals == 0).mean() * 100), 2),
        "nan_pct": round(float(np.isnan(vals).mean() * 100), 2),
        "total_observations": int(vals.size),
        "geographic": geo,
    }


def inspect_graph(path):
    import pickle
    with open(path, "rb") as fh:
        G = pickle.load(fh)
    lats = np.array([float(d["y"]) for _, d in G.nodes(data=True)])
    lons = np.array([float(d["x"]) for _, d in G.nodes(data=True)])
    _u, _v, _k, sample = next(iter(G.edges(keys=True, data=True)))
    hw = Counter()
    for _a, _b, _c, d in G.edges(keys=True, data=True):
        h = d.get("highway")
        hw[str(h[0] if isinstance(h, list) else h)] += 1
    return {
        "kind": "graph",
        "nodes": G.number_of_nodes(), "edges": G.number_of_edges(),
        "edge_attributes": sorted(sample.keys()),
        "bbox": [float(lons.min()), float(lats.min()), float(lons.max()), float(lats.max())],
        "extent_km": [round((lons.max() - lons.min()) * 106, 1),
                      round((lats.max() - lats.min()) * 111, 1)],
        "highway_mix": dict(hw.most_common(10)),
    }


def inspect_document(path):
    """Word/PDF-only 'datasets' -- record that they carry no machine-readable rows."""
    docs = []
    for f in sorted(path.rglob("*")):
        if f.suffix.lower() not in (".docx", ".doc", ".pdf"):
            continue
        entry = {"file": f.name, "size": human(f.stat().st_size)}
        if f.suffix.lower() == ".docx":
            try:
                z = zipfile.ZipFile(f)
                media = [i for i in z.infolist() if i.filename.startswith("word/media/")]
                xml = z.read("word/document.xml").decode("utf8", errors="ignore")
                text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xml))
                entry.update({
                    "embedded_images": len(media),
                    "chart_objects_emf": sum(1 for m in media if m.filename.endswith(".emf")),
                    "text_chars": len(text),
                    "has_data_tables": "<w:tbl>" in xml,
                })
            except Exception as exc:
                entry["error"] = str(exc)
        docs.append(entry)
    return {"kind": "document", "documents": docs,
            "machine_readable_rows": 0}


def inspect_vision_segmentation(path):
    from PIL import Image
    splits, class_frames, sizes = {}, Counter(), Counter()
    for split in ("train", "val", "test"):
        imgs = sorted((path / "images" / split).glob("*")) if (path / "images" / split).exists() else []
        labs = sorted((path / "label" / split).glob("*_label.png")) if (path / "label" / split).exists() else []
        splits[split] = {"images": len(imgs), "semantic_labels": len(labs)}
        for im in imgs[:50]:
            try:
                sizes[Image.open(im).size] += 1
            except Exception:
                pass
        for lb in labs[:300]:                       # class presence per frame
            try:
                class_frames.update(np.unique(np.array(Image.open(lb))).tolist())
            except Exception:
                pass
    sampled = sum(min(300, splits[s]["semantic_labels"]) for s in splits)
    return {
        "kind": "vision_segmentation",
        "splits": splits,
        "image_sizes": {str(k): v for k, v in sizes.most_common(5)},
        "annotation_type": "per-pixel semantic mask (PNG)",
        "bounding_boxes": False,
        "classes": {str(k): {"name": IDD_LITE_CLASSES.get(int(k), "?"),
                             "frames_present": v,
                             "frame_pct": round(v / max(sampled, 1) * 100, 1)}
                    for k, v in sorted(class_frames.items())},
        "n_classes_excl_ignore": len([k for k in class_frames if int(k) != 255]),
    }


def inspect_vision_detection(path):
    imgs = [p for p in path.rglob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png")]
    txt = [p for p in path.rglob("*.txt") if p.name != "classes.txt"]
    xml = list(path.rglob("*.xml"))
    cls = Counter()
    for t in txt[:2000]:
        try:
            for line in t.read_text().strip().splitlines():
                if line.strip():
                    cls[line.split()[0]] += 1
        except Exception:
            pass
    return {
        "kind": "vision_detection",
        "images": len(imgs), "yolo_txt": len(txt), "pascal_xml": len(xml),
        "annotation_coverage_pct": round(len(txt) / max(len(imgs), 1) * 100, 1),
        "class_ids_seen": len(cls),
        "box_count_by_class": dict(cls.most_common(20)),
    }


DISPATCH = {
    "tabular": inspect_tabular,
    "timeseries": inspect_timeseries,
    "graph": inspect_graph,
    "document": inspect_document,
    "vision_segmentation": inspect_vision_segmentation,
    "vision_detection": inspect_vision_detection,
}


def inspect_all(cfg_path=None):
    cfg = yaml.safe_load((cfg_path or BACKEND / "config/datasets.yaml").read_text())
    REPORTS.mkdir(parents=True, exist_ok=True)
    results = {}
    for name, meta in cfg["sources"].items():
        path = resolve(meta["path"])
        rec = {"registry": meta, "path": str(path), "exists": path.exists()}
        if not path.exists():
            rec["status"] = meta.get("status", "MISSING")
            print("  [--] %-26s %s" % (name, rec["status"]))
        else:
            rec["size"] = human(dir_size(path))
            try:
                rec["inspection"] = DISPATCH[meta["kind"]](path)
                print("  [ok] %-26s %-10s %s" % (name, meta["kind"], rec["size"]))
            except Exception as exc:
                rec["error"] = "%s: %s" % (type(exc).__name__, exc)
                print("  [!!] %-26s %s" % (name, rec["error"]))
        results[name] = rec
    (REPORTS / "inspection.json").write_text(json.dumps(results, indent=2, default=str))
    return results


if __name__ == "__main__":
    inspect_all()
