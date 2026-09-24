#!/usr/bin/env python3
import os

# --- Paths & Configuration ---
BASE_SEARCH_DIR = "/home/kkacanja/sub-solar-search/O4b/search/singles/search"
FULL_DATA_DIR   = "/home/kkacanja/sub-solar-search/O4b/search/singles/full_data"
GLOBAL_VETO_FILE = "/home/kkacanja/sub-solar-search/O4b/search/singles/GLOBAL_VETOES.xml"
BANKS_BASE_DIR  = "/home/kkacanja/sub-solar-search/banks/26sub"
PYCBC_BIN       = "/home/kkacanja/miniconda3/envs/fir/bin"

SNR_THRESH      = "6.0"
NUM_SPLITS      = 4
DETECTORS       = ["H1", "L1"]
SUBSEARCH_IDS   = list(range(1, 27))

def write_fitby(sub_dir, s_id):
    sh_content = f"""#!/bin/bash
set -e
IFO=$1

if [ -z "$IFO" ]; then
    echo "Usage: ./fitby.sh [H1|L1]"
    exit 1
fi

TRIG_FILE="{FULL_DATA_DIR}/{s_id}/cleaned2/${{IFO}}-HDF_TRIGGER_MERGE_FULL_DATA_SNR{SNR_THRESH}.hdf"
BANK_FILE="{BANKS_BASE_DIR}/{s_id}/merged/FIR_BANK_MERGED_FLAT.hdf"
VETO_FILE="{GLOBAL_VETO_FILE}"
OUT_FILE="${{IFO}}-FIT_BY_TEMPLATE_FULL_DATA.hdf"

{PYCBC_BIN}/pycbc_fit_sngls_by_template \\
    --fit-function exponential \\
    --stat-threshold 6.0 \\
    --prune-param mtotal \\
    --log-prune-param \\
    --prune-bins 2 \\
    --prune-number 2 \\
    --sngl-ranking newsnr_sgveto_psdvar_scaled_threshold \\
    --ifo ${{IFO}} \\
    --trigger-file ${{TRIG_FILE}} \\
    --bank-file ${{BANK_FILE}} \\
    --veto-file ${{VETO_FILE}} \\
    --veto-segment-name vetoes \\
    --output ${{OUT_FILE}}
"""
    sh_path = os.path.join(sub_dir, "fitby.sh")
    with open(sh_path, "w") as f:
        f.write(sh_content)
    os.chmod(sh_path, 0o755)

    sub_content = f"""universe = vanilla
executable = fitby.sh
arguments = $(ifo)
getenv = True

output = logs/fitby_$(ifo).out
error  = logs/fitby_$(ifo).err
log    = logs/fitby_$(ifo).log

request_cpus = 1
request_memory = 16 GB
request_disk = 10 GB

queue ifo in (H1, L1)
"""
    with open(os.path.join(sub_dir, "fitby.sub"), "w") as f:
        f.write(sub_content)

def write_fitover(sub_dir, s_id):
    sh_content = f"""#!/bin/bash
set -e
IFO=$1

if [ -z "$IFO" ]; then
    echo "Usage: ./fitover.sh [H1|L1]"
    exit 1
fi

TEMPLATE_FIT="${{IFO}}-FIT_BY_TEMPLATE_FULL_DATA.hdf"
BANK_FILE="{BANKS_BASE_DIR}/{s_id}/merged/FIR_BANK_MERGED_FLAT.hdf"
OUT_FILE="${{IFO}}-FIT_OVER_PARAM_FULL_DATA.hdf"

{PYCBC_BIN}/pycbc_fit_sngls_over_multiparam \\
    --fit-param mtotal \\
    --f-lower 20 \\
    --log-param True \\
    --smoothing-width 0.4 \\
    --template-fit-file ${{TEMPLATE_FIT}} \\
    --bank-file ${{BANK_FILE}} \\
    --output ${{OUT_FILE}}
"""
    sh_path = os.path.join(sub_dir, "fitover.sh")
    with open(sh_path, "w") as f:
        f.write(sh_content)
    os.chmod(sh_path, 0o755)

    sub_content = f"""universe = vanilla
executable = fitover.sh
arguments = $(ifo)
getenv = True

output = logs/fitover_$(ifo).out
error  = logs/fitover_$(ifo).err
log    = logs/fitover_$(ifo).log

request_cpus = 1
request_memory = 16 GB
request_disk = 10 GB

queue ifo in (H1, L1)
"""
    with open(os.path.join(sub_dir, "fitover.sub"), "w") as f:
        f.write(sub_content)

def write_sngls(sub_dir, s_id):
    sh_content = f"""#!/bin/bash
set -e
IFO=$1
PART=$2
NUM_PARTS=$3

if [ -z "$IFO" ] || [ -z "$PART" ] || [ -z "$NUM_PARTS" ]; then
    echo "Usage: ./sngls.sh [H1|L1] [PART_IDX] [NUM_PARTS]"
    exit 1
fi

TRIG_FILE="{FULL_DATA_DIR}/{s_id}/cleaned2/${{IFO}}-HDF_TRIGGER_MERGE_FULL_DATA_SNR{SNR_THRESH}.hdf"
BANK_FILE="{BANKS_BASE_DIR}/{s_id}/merged/FIR_BANK_MERGED_FLAT.hdf"
VETO_FILE="{GLOBAL_VETO_FILE}"
OUT_FILE="${{IFO}}-SNGLS_FULL_DATA_1DET_JOB${{PART}}.hdf"

{PYCBC_BIN}/pycbc_sngls_findtrigs \\
    --trigger-cuts newsnr:6.0:lower traditional_chisq:1.2:upper sigma_multiple:5:upper \\
    --ranking-statistic exp_fit \\
    --statistic-features phasetd sensitive_volume normalize_fit_rate \\
    --statistic-keywords alpha_below_thresh:6 \\
    --sngl-ranking newsnr_sgveto_psdvar_scaled_threshold \\
    --randomize-template-order \\
    --template-bank ${{BANK_FILE}} \\
    --trigger-files ${{TRIG_FILE}} \\
    --statistic-files H1-FIT_OVER_PARAM_FULL_DATA.hdf L1-FIT_OVER_PARAM_FULL_DATA.hdf \\
    --veto-files ${{VETO_FILE}} \\
    --segment-name vetoes \\
    --template-fraction-range ${{PART}}/${{NUM_PARTS}} \\
    --output-file ${{OUT_FILE}}
"""
    sh_path = os.path.join(sub_dir, "sngls.sh")
    with open(sh_path, "w") as f:
        f.write(sh_content)
    os.chmod(sh_path, 0o755)

    sub_content = f"""universe = vanilla
executable = sngls.sh
arguments = $(ifo) $(part) {NUM_SPLITS}
getenv = True

output = logs/sngls_$(ifo)_job$(part).out
error  = logs/sngls_$(ifo)_job$(part).err
log    = logs/sngls_$(ifo)_job$(part).log

request_cpus = 1
request_memory = 16 GB
request_disk = 10 GB

queue ifo,part from (
    H1, 0
    H1, 1
    H1, 2
    H1, 3
    L1, 0
    L1, 1
    L1, 2
    L1, 3
)
"""
    with open(os.path.join(sub_dir, "sngls.sub"), "w") as f:
        f.write(sub_content)

def write_sngls_statmap(sub_dir, s_id):
    sh_content = f"""#!/bin/bash
set -e
IFO=$1

if [ -z "$IFO" ]; then
    echo "Usage: ./sngls_statmap.sh [H1|L1]"
    exit 1
fi

FILES=$(ls ${{IFO}}-SNGLS_FULL_DATA_1DET_JOB*.hdf 2>/dev/null)
if [ -z "$FILES" ]; then
    echo "Error: No ${{IFO}}-SNGLS_FULL_DATA_1DET_JOB*.hdf files found."
    exit 1
fi

OUT_FILE="${{IFO}}-SNGLS_STATMAP_FULL_DATA_1DET.hdf"

{PYCBC_BIN}/pycbc_sngls_statmap \\
    --max-hierarchical-removal 1 \\
    --hierarchical-removal-against exclusive \\
    --veto-window 0.100 \\
    --cluster-window 10.0 \\
    --far-calculation-method H1:trigger_fit L1:trigger_fit \\
    --fit-function H1:exponential L1:exponential \\
    --fit-threshold H1:13 L1:13 \\
    --sngls-files $FILES \\
    --ifos ${{IFO}} \\
    --output-file ${{OUT_FILE}}
"""
    sh_path = os.path.join(sub_dir, "sngls_statmap.sh")
    with open(sh_path, "w") as f:
        f.write(sh_content)
    os.chmod(sh_path, 0o755)

    sub_content = f"""universe = vanilla
executable = sngls_statmap.sh
arguments = $(ifo)
getenv = True

output = logs/sngls_statmap_$(ifo).out
error  = logs/sngls_statmap_$(ifo).err
log    = logs/sngls_statmap_$(ifo).log

request_cpus = 2
request_memory = 16 GB
request_disk = 10 GB

queue ifo in (H1, L1)
"""
    with open(os.path.join(sub_dir, "sngls_statmap.sub"), "w") as f:
        f.write(sub_content)

def main():
    print(f"Generating singles scripts with GLOBAL_VETOES for sub-searches 1 to 26...")
    for s_id in SUBSEARCH_IDS:
        sub_dir = os.path.join(BASE_SEARCH_DIR, str(s_id))
        os.makedirs(sub_dir, exist_ok=True)
        os.makedirs(os.path.join(sub_dir, "logs"), exist_ok=True)

        write_fitby(sub_dir, s_id)
        write_fitover(sub_dir, s_id)
        write_sngls(sub_dir, s_id)
        write_sngls_statmap(sub_dir, s_id)

        print(f"  [✓] Configured sub-search {s_id:02d} -> {sub_dir}")

    print("\n[✓] Generated all workflow files with vetoes.")

if __name__ == "__main__":
    main()
