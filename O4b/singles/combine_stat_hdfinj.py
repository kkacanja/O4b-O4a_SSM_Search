#!/usr/bin/env python3
import glob
import os
import re

BASE_SEARCH_DIR = "/home/kkacanja/sub-solar-search/O4b/search/singles/search"
SINGLES_INJ_DIR = (
    "/home/kkacanja/sub-solar-search/O4b/search/singles/injections"
)
GLOBAL_VETO_FILE = (
    "/home/kkacanja/sub-solar-search/O4b/search/GLOBAL_VETOES.xml"
)
CLUSTER_WINDOW = 10.0
INJ_WINDOW = 2.0


def get_target_searches():
  searches = []
  if os.path.exists(BASE_SEARCH_DIR):
    for d in os.listdir(BASE_SEARCH_DIR):
      if d.isdigit():
        searches.append(int(d))
  return sorted(searches)


def discover_tags_for_search(search_id, s_dir):
  """Discovers BNS tags from optimal SNR merge files or local single job files."""
  tags = set()
  # 1. Check optimal SNR merge directory
  opt_dir = os.path.join(SINGLES_INJ_DIR, str(search_id))
  for f in glob.glob(
      os.path.join(opt_dir, "H1L1-OPTIMAL_SNR_MERGE_*_INJECTIONS.hdf")
  ):
    m = re.search(r"MERGE_(BNS[^_]+)_INJECTIONS", os.path.basename(f))
    if m:
      tags.add(m.group(1))
  # 2. Check local search directory
  for f in glob.glob(os.path.join(s_dir, "H1-SNGLS_BNS*_INJECTIONS*.hdf")):
    m = re.search(r"H1-SNGLS_(BNS[^_]+)_INJECTIONS", os.path.basename(f))
    if m:
      tags.add(m.group(1))
  return sorted(list(tags))


def generate_scripts_for_search(search_id):
  s_dir = os.path.join(BASE_SEARCH_DIR, str(search_id))
  if not os.path.exists(s_dir):
    return

  tags = discover_tags_for_search(search_id, s_dir)
  if not tags:
    print(
        f"[!] Warning: No injection tags found for search {search_id:02d},"
        " skipping script generation."
    )
    return

  # --- 1. Generate combine_statmap.sh ---
  combine_sh_path = os.path.join(s_dir, "combine_statmap.sh")
  with open(combine_sh_path, "w") as f_sh:
    f_sh.write("#!/bin/bash\nset -e\n\n")

    f_sh.write("echo '=== Combining Full Data Singles Statmap ==='\n")
    f_sh.write(
        f"pycbc_add_statmap \\\n"
        f"    --cluster-window {CLUSTER_WINDOW} \\\n"
        f"    --far-calculation-method H1:trigger_fit L1:trigger_fit \\\n"
        f"    --fit-function H1:exponential L1:exponential \\\n"
        f"    --fit-threshold H1:13 L1:13 \\\n"
        f"    --statmap-files H1-SNGLS_STATMAP_FULL_DATA_1DET.hdf"
        f" L1-SNGLS_STATMAP_FULL_DATA_1DET.hdf \\\n"
        f"    --output-file H1L1-SNGLS_COMBINE_STATMAP_FULL_DATA.hdf\n\n"
    )

    for tag in tags:
      f_sh.write(
          f"echo '=== Combining Singles Statmap for {tag} Injections ==='\n"
      )
      f_sh.write(
          f"pycbc_add_statmap \\\n"
          f"    --cluster-window {CLUSTER_WINDOW} \\\n"
          f"    --far-calculation-method H1:trigger_fit L1:trigger_fit \\\n"
          f"    --fit-function H1:exponential L1:exponential \\\n"
          f"    --fit-threshold H1:13 L1:13 \\\n"
          f"    --background-files H1-EXCLUDE_ZEROLAG_FULL_DATA_1DET.hdf"
          f" L1-EXCLUDE_ZEROLAG_FULL_DATA_1DET.hdf \\\n"
          f"    --statmap-files H1-SNGLS_STATMAP_INJ_{tag}_INJECTIONS_1DET.hdf"
          f" L1-SNGLS_STATMAP_INJ_{tag}_INJECTIONS_1DET.hdf \\\n"
          f"    --output-file"
          f" H1L1-SNGLS_COMBINE_STATMAP_{tag}_INJECTIONS.hdf\n\n"
      )

  os.chmod(combine_sh_path, 0o755)

  # --- 2. Generate hdfinjfind.sh ---
  injfind_sh_path = os.path.join(s_dir, "hdfinjfind.sh")
  with open(injfind_sh_path, "w") as f_inj:
    f_inj.write("#!/bin/bash\nset -e\n\n")

    for tag in tags:
      opt_file = os.path.join(
          SINGLES_INJ_DIR,
          str(search_id),
          f"H1L1-OPTIMAL_SNR_MERGE_{tag}_INJECTIONS.hdf",
      )
      veto_flag = (
          f"--veto-file {GLOBAL_VETO_FILE} --segment-name closed_box"
          if os.path.exists(GLOBAL_VETO_FILE)
          else ""
      )

      f_inj.write(f"echo '=== Running HDF Injection Find for {tag} ==='\n")
      f_inj.write(
          f"pycbc_coinc_hdfinjfind \\\n"
          f"    --injection-window {INJ_WINDOW} \\\n"
          f"    --optimal-snr-column H1:optimal_snr_H1 L1:optimal_snr_L1 \\\n"
          f"    --trigger-file"
          f" H1L1-SNGLS_COMBINE_STATMAP_{tag}_INJECTIONS.hdf \\\n"
          f"    --injection-file {opt_file} \\\n"
          f"    {veto_flag} \\\n"
          f"    --output-file H1L1-SNGLS_HDFINJFIND_{tag}_INJECTIONS.hdf \\\n"
          f"    --verbose\n\n"
      )

  os.chmod(injfind_sh_path, 0o755)

  # --- 3. Generate HTCondor Submit Files ---
  os.makedirs(os.path.join(s_dir, "logs"), exist_ok=True)

  with open(os.path.join(s_dir, "combine_statmap.sub"), "w") as f_sub:
    f_sub.write(
        f"universe = vanilla\n"
        f"executable = {combine_sh_path}\n"
        f"getenv = True\n"
        f"output = logs/combine_statmap.out\n"
        f"error = logs/combine_statmap.err\n"
        f"log = logs/combine_statmap.log\n"
        f"request_memory = 32 GB\n"
        f"request_cpus = 1\n"
        f"batch_name = sngls_combine_{search_id}\n"
        f"queue\n"
    )

  with open(os.path.join(s_dir, "hdfinjfind.sub"), "w") as f_sub:
    f_sub.write(
        f"universe = vanilla\n"
        f"executable = {injfind_sh_path}\n"
        f"getenv = True\n"
        f"output = logs/hdfinjfind.out\n"
        f"error = logs/hdfinjfind.err\n"
        f"log = logs/hdfinjfind.log\n"
        f"request_memory = 32 GB\n"
        f"request_cpus = 1\n"
        f"batch_name = sngls_injfind_{search_id}\n"
        f"queue\n"
    )

  print(
      f"[✓] Configured search {search_id:02d} -> {len(tags)} injection sets:"
      f" {tags}"
  )


def main():
  for sid in get_target_searches():
    generate_scripts_for_search(sid)


if __name__ == "__main__":
  main()
