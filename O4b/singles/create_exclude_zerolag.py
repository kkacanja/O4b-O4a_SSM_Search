#!/usr/bin/env python3
import os
import glob
import re

TARGET_SEARCHES = range(1,27,1)
#[1, 3, 9, 20, 26]
BASE_SEARCH_DIR = "/home/kkacanja/sub-solar-search/O4b/search/singles/search"
O4b_SEARCH_BASE = "/home/kkacanja/sub-solar-search/O4b/search"
DETECTORS = ["H1", "L1"]


def generate_exclude_zerolag_for_search(search_id):
    s_dir = os.path.join(BASE_SEARCH_DIR, str(search_id))
    if not os.path.exists(s_dir):
        print(f"[!] Directory not found: {s_dir}")
        return

    # Check for the local full data singles statmaps
    h1_statmap = os.path.join(s_dir, "H1-SNGLS_STATMAP_FULL_DATA_1DET.hdf")
    l1_statmap = os.path.join(s_dir, "L1-SNGLS_STATMAP_FULL_DATA_1DET.hdf")


    # Discover the full data 2DET coinc statmap file from the search chunk
    coinc_pattern = os.path.join(
        O4b_SEARCH_BASE, str(search_id), "O4b*", "output",
        "H1L1-STATMAP_FULL_DATA_2DET-*.hdf"
    )
    coinc_files = sorted(glob.glob(coinc_pattern))
    
    # Fallback to search_path without wildcards if merged
    if not coinc_files:
        coinc_pattern = os.path.join(
            O4b_SEARCH_BASE, str(search_id), "O4b*", "output",
            "*-STATMAP_FULL_DATA_2DET*.hdf"
        )
        coinc_files = sorted(glob.glob(coinc_pattern))

    coinc_2det_arg = coinc_files[0] if coinc_files else None

    # --- 1. Generate exclude_zerolag.sh ---
    sh_path = os.path.join(s_dir, "exclude_zerolag.sh")
    with open(sh_path, "w") as f_sh:
        f_sh.write("#!/bin/bash\nset -e\n\n")

        # Command for H1
        other_files_h1 = f"{coinc_2det_arg} L1-SNGLS_STATMAP_FULL_DATA_1DET.hdf" if coinc_2det_arg else "L1-SNGLS_STATMAP_FULL_DATA_1DET.hdf"
        f_sh.write("echo '=== Running pycbc_exclude_zerolag for H1 ==='\n")
        f_sh.write(
            f"pycbc_exclude_zerolag \\\n"
            f"    --far-calculation-method H1:trigger_fit L1:trigger_fit \\\n"
            f"    --fit-function H1:exponential L1:exponential \\\n"
            f"    --fit-threshold H1:13 L1:13 \\\n"
            f"    --statmap-file H1-SNGLS_STATMAP_FULL_DATA_1DET.hdf \\\n"
            f"    --other-statmap-files {other_files_h1} \\\n"
            f"    --output-file H1-EXCLUDE_ZEROLAG_FULL_DATA_1DET.hdf\n\n"
        )

        # Command for L1
        other_files_l1 = f"{coinc_2det_arg} H1-SNGLS_STATMAP_FULL_DATA_1DET.hdf" if coinc_2det_arg else "H1-SNGLS_STATMAP_FULL_DATA_1DET.hdf"
        f_sh.write("echo '=== Running pycbc_exclude_zerolag for L1 ==='\n")
        f_sh.write(
            f"pycbc_exclude_zerolag \\\n"
            f"    --far-calculation-method H1:trigger_fit L1:trigger_fit \\\n"
            f"    --fit-function H1:exponential L1:exponential \\\n"
            f"    --fit-threshold H1:13 L1:13 \\\n"
            f"    --statmap-file L1-SNGLS_STATMAP_FULL_DATA_1DET.hdf \\\n"
            f"    --other-statmap-files {other_files_l1} \\\n"
            f"    --output-file L1-EXCLUDE_ZEROLAG_FULL_DATA_1DET.hdf\n\n"
        )

    os.chmod(sh_path, 0o755)

    # --- 2. Generate exclude_zerolag.sub ---
    log_dir = os.path.join(s_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    sub_path = os.path.join(s_dir, "exclude_zerolag.sub")

    with open(sub_path, "w") as f_sub:
        f_sub.write(
            f"universe = vanilla\n"
            f"executable = {sh_path}\n"
            f"getenv = True\n"
            f"output = logs/exclude_zerolag.out\n"
            f"error = logs/exclude_zerolag.err\n"
            f"log = logs/exclude_zerolag.log\n"
            f"request_memory = 32 GB\n"
            f"request_cpus = 1\n"
            f"batch_name = sngls_excl_zerolag_{search_id}\n"
            f"queue\n"
        )

    print(f"[✓] Search {search_id:02d} -> Created exclude_zerolag.sh and exclude_zerolag.sub")
    if not coinc_2det_arg:
        print(f"    [Warning] No 2DET coinc statmap found; running with single-detector cross-exclusion only.")


def main():
    for sid in TARGET_SEARCHES:
        generate_exclude_zerolag_for_search(sid)


if __name__ == "__main__":
    main()
