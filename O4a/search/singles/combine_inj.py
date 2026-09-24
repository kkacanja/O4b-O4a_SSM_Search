#!/usr/bin/env python3
import gc
import glob
import os
import re
import sys
import h5py
import numpy as np

# --- Configuration ---
BASE_SEARCH_DIR = "/home/kkacanja/sub-solar-search/O4a/search"
OUTPUT_DIR = "/home/kkacanja/sub-solar-search/O4a/search/singles/injections"
BANKS_BASE_DIR = "/home/kkacanja/sub-solar-search/banks/26sub"
DETECTORS = ["H1", "L1"]
IGNORED_SEARCHES = [2]

# Allow running a specific search via CLI (e.g. `python combine_inj_triggers.py 1`)
if len(sys.argv) > 1:
  SEARCH_IDS = [int(sys.argv[1])]
else:
  SEARCH_IDS = [s for s in range(1, 27) if s not in IGNORED_SEARCHES]

os.makedirs(OUTPUT_DIR, exist_ok=True)


def discover_injection_tags(search_id):
  """
  Finds all unique injection tags (e.g., 'BNS0.7_0', 'BNS0.7_2000', 'BNS1.1_0') present in the chunks.
  """
  search_path = os.path.join(BASE_SEARCH_DIR, str(search_id))
  coinc_dirs = glob.glob(
      os.path.join(search_path, "O4a*", "output_FINJ", "*_coinc")
  )

  tags = set()
  for d in coinc_dirs:
    dirname = os.path.basename(d)
    tag = dirname.replace("_coinc", "")
    # Ignore corrected or non-standard directory tags
    if "CORRECTED" not in tag.upper():
      tags.add(tag)

  return sorted(list(tags))


def group_tags_by_base(tags):
  """
  Groups tags like ['BNS0.7_0', 'BNS0.7_2000'] into {'BNS0.7': ['BNS0.7_0', 'BNS0.7_2000']}.
  """
  grouped = {}
  for t in tags:
    # Match base prefix like BNS0.7 or BNS1.1
    m = re.match(r"(BNS[0-9.]+)", t)
    base = m.group(1) if m else t
    grouped.setdefault(base, []).append(t)
  return grouped


def combine_injections_for_tag(search_id, base_tag, tag_list, detector):
  # Match standard trigger merge files across all sub-tags belonging to this base tag
  raw_files = []
  for t in tag_list:
    file_pattern = os.path.join(
        BASE_SEARCH_DIR,
        str(search_id),
        "O4a*",
        "output_FINJ",
        f"{t}_coinc",
        f"{detector}-HDF_TRIGGER_MERGE_{t}_INJECTIONS-*.hdf",
    )
    raw_files.extend(glob.glob(file_pattern))

  input_files = sorted(
      [f for f in raw_files if "CORRECTED" not in os.path.basename(f)]
  )

  if not input_files:
    print(f"  [{detector}][{base_tag}] No trigger merge files found.")
    return

  print(f"\n=======================================================")
  print(
      f"  [Search {search_id:02d}][{detector}][{base_tag}] Found"
      f" {len(input_files)} total chunk files across sub-tags: {tag_list}"
  )
  print(f"=======================================================")

  search_out_dir = os.path.join(OUTPUT_DIR, str(search_id), base_tag)
  os.makedirs(search_out_dir, exist_ok=True)
  output_filepath = os.path.join(
      search_out_dir, f"{detector}-HDF_TRIGGER_MERGE_{base_tag}_INJECTIONS.hdf"
  )

  # 1. Discover total number of templates from bank or first chunk
  bank_path = os.path.join(
      BANKS_BASE_DIR, str(search_id), "merged", "FIR_BANK_MERGED_FLAT.hdf"
  )
  if os.path.exists(bank_path):
    with h5py.File(bank_path, "r") as fb:
      num_templates = (
          len(fb["mass1"]) if "mass1" in fb else len(fb["template_hash"])
      )
  else:
    with h5py.File(input_files[0], "r") as f0:
      num_templates = f0[f"{detector}/template_boundaries"].shape[0]

  # --- PASS 1: Scan template IDs, subgroups & metadata (No SNR threshold) ---
  print(f"[Pass 1/2] Scanning chunks (extracting all triggers)...")
  chunk_template_ids = []
  valid_files = []

  search_data = {}
  gating_data = {}
  root_attrs = {}
  group_attrs = {}

  for idx, filepath in enumerate(input_files, 1):
    fname = os.path.basename(filepath)
    try:
      with h5py.File(filepath, "r") as f_in:
        if detector not in f_in or "snr" not in f_in[detector]:
          continue

        det_in = f_in[detector]

        if not root_attrs:
          root_attrs = dict(f_in.attrs)
          group_attrs = dict(det_in.attrs)

        # Collect search/ metadata
        if "search" in det_in:
          for k in det_in["search"].keys():
            if isinstance(det_in["search"][k], h5py.Dataset):
              search_data.setdefault(k, []).append(det_in["search"][k][:])

        # Collect gating/auto/ metadata
        if "gating/auto" in det_in:
          for k in det_in["gating/auto"].keys():
            if isinstance(det_in["gating/auto"][k], h5py.Dataset):
              gating_data.setdefault(k, []).append(det_in["gating/auto"][k][:])

        t_ids = det_in["template_id"][:].astype(np.int32)
        n_trigs = len(t_ids)

        if n_trigs > 0:
          chunk_template_ids.append(t_ids)
          valid_files.append(filepath)

        print(
            f"  [{idx:02d}/{len(input_files):02d}] {fname} ->"
            f" {n_trigs:,} triggers",
            flush=True,
        )

    except Exception as err:
      print(f"    Warning: Skipping file {fname} due to error: {err}")
      continue

  if not chunk_template_ids:
    print(f"  [!] No triggers found for {detector} ({base_tag}).")
    return

  # Global sort across all chunks
  all_template_ids = np.concatenate(chunk_template_ids, axis=0)
  del chunk_template_ids
  gc.collect()

  total_triggers = len(all_template_ids)
  print(f"\n[+] Total Ingested Triggers: {total_triggers:,}")
  print(
      f"[+] Sorting template boundaries for {num_templates:,} templates...",
      flush=True,
  )

  sort_indices = np.argsort(all_template_ids, kind="stable").astype(np.int32)
  all_template_ids_sorted = all_template_ids[sort_indices]
  del all_template_ids
  gc.collect()

  bnds = np.searchsorted(all_template_ids_sorted, np.arange(num_templates + 1))
  template_boundaries = bnds[:-1].astype(np.int64)
  active_templates = np.where(bnds[1:] > bnds[:-1])[0]
  print(f"[+] Active Templates with Triggers: {len(active_templates):,}")

  # Discover all 1D trigger column names
  with h5py.File(valid_files[0], "r") as f0:
    det0 = f0[detector]
    n_first = det0["snr"].shape[0]
    trig_keys = [
        k
        for k in det0.keys()
        if isinstance(det0[k], h5py.Dataset)
        and det0[k].shape == (n_first,)
        and not k.endswith("_template")
        and k != "template_boundaries"
    ]

  # --- PASS 2: Write Merged Output & Rebuild Region References ---
  print(
      f"\n[Pass 2/2] Writing datasets and generating references in"
      f" {output_filepath}...",
      flush=True,
  )
  try:
    ref_type = h5py.regionref_dtype
  except AttributeError:
    ref_type = h5py.special_dtype(ref=h5py.RegionReference)

  with h5py.File(output_filepath, "w") as f_out:
    # Write root & detector attributes
    for k, v in root_attrs.items():
      f_out.attrs[k] = v

    det_out = f_out.create_group(detector)
    for k, v in group_attrs.items():
      det_out.attrs[k] = v

    # Write concatenated search/ datasets
    if search_data:
      s_grp = det_out.create_group("search")
      for k, val_list in search_data.items():
        s_grp.create_dataset(
            k, data=np.concatenate(val_list, axis=0), chunks=True
        )
    del search_data
    gc.collect()

    # Write concatenated gating/auto/ datasets
    if gating_data:
      g_auto = det_out.create_group("gating/auto")
      for k, val_list in gating_data.items():
        g_auto.create_dataset(
            k, data=np.concatenate(val_list, axis=0), chunks=True
        )
    del gating_data
    gc.collect()

    # Write template_boundaries
    det_out.create_dataset(
        "template_boundaries",
        data=template_boundaries,
        compression="gzip",
        compression_opts=1,
    )

    # Write sorted template_id
    det_out.create_dataset(
        "template_id",
        data=all_template_ids_sorted.astype(np.int64),
        compression="gzip",
        compression_opts=1,
    )
    del all_template_ids_sorted
    gc.collect()
    f_out.flush()

    # Stream all 1D trigger columns and generate fresh region references
    cols_to_write = [k for k in trig_keys if k != "template_id"]

    for c_idx, col_name in enumerate(cols_to_write, 1):
      print(
          f"  [{c_idx:02d}/{len(cols_to_write):02d}] Extracting & writing:"
          f" '{col_name}'...",
          flush=True,
      )

      col_chunks = []
      for fpath in valid_files:
        with h5py.File(fpath, "r") as f_in:
          col_chunks.append(f_in[f"{detector}/{col_name}"][:])

      col_all = np.concatenate(col_chunks, axis=0)
      del col_chunks
      gc.collect()

      col_sorted = col_all[sort_indices]
      del col_all
      gc.collect()

      # Write 1D dataset
      dset = det_out.create_dataset(
          col_name,
          data=col_sorted,
          maxshape=(None,),
          dtype=col_sorted.dtype,
          chunks=True,
          compression="gzip",
          compression_opts=1,
      )
      del col_sorted
      gc.collect()

      # Rebuild Region References pointing directly to this new dataset
      ref_array = np.empty(num_templates, dtype=ref_type)
      ref_array[:] = dset.regionref[0:0]

      for t_idx in active_templates:
        ref_array[t_idx] = dset.regionref[bnds[t_idx] : bnds[t_idx + 1]]

      det_out.create_dataset(
          f"{col_name}_template",
          data=ref_array,
          dtype=ref_type,
          compression="gzip",
          compression_opts=1,
      )
      del ref_array
      f_out.flush()
      gc.collect()

  del sort_indices
  gc.collect()
  print(f"[✓] Successfully generated {detector} -> {output_filepath}\n")


def main():
  print(f"Starting injection trigger merge for subsearches: {SEARCH_IDS}\n")
  for s_id in SEARCH_IDS:
    inj_tags = discover_injection_tags(s_id)
    if not inj_tags:
      print(f"[Search {s_id:02d}] No injection folders found, skipping.")
      continue

    base_groups = group_tags_by_base(inj_tags)

    print(f"\n=======================================================")
    print(f"Processing Subsearch {s_id:02d} -> Base injection groups:")
    for b, t_list in base_groups.items():
      print(f"  {b}: {t_list}")
    print(f"=======================================================")

    for base_tag, tag_list in base_groups.items():
      for det in DETECTORS:
        combine_injections_for_tag(s_id, base_tag, tag_list, det)


if __name__ == "__main__":
  main()
