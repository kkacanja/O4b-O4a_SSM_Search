#!/usr/bin/env python3
import os

# --- Paths & Configuration ---
BASE_SEARCH_DIR  = "/home/kkacanja/sub-solar-search/O4a/search/singles/search"
INJ_DATA_DIR     = "/home/kkacanja/sub-solar-search/O4a/search/singles/injections"
GLOBAL_VETO_FILE = "/home/kkacanja/sub-solar-search/O4a/search/singles/GLOBAL_VETOES.xml"
BANKS_BASE_DIR   = "/home/kkacanja/sub-solar-search/banks/26sub"
PYCBC_BIN        = "/home/kkacanja/miniconda3/envs/fir/bin"

NUM_SPLITS       = 4
DETECTORS        = ["H1", "L1"]

INJECTION_MAPPING = {
    1: ["0.7", "1.1", "1.2"],
    3: ["0.5"],
    9: ["0.35"],
    20: ["0.2"],
    26: ["0.1"]
}

def write_sngls_inj(sub_dir, s_id, tags):
    sh_content = f"""#!/bin/bash
set -e
IFO=$1
TAG=$2
PART=$3
NUM_PARTS=$4

if [ -z "$IFO" ] || [ -z "$TAG" ] || [ -z "$PART" ] || [ -z "$NUM_PARTS" ]; then
    echo "Usage: ./sngls_inj.sh [H1|L1] [TAG] [PART_IDX] [NUM_PARTS]"
    exit 1
fi

TRIG_FILE="{INJ_DATA_DIR}/{s_id}/${{IFO}}-HDF_TRIGGER_MERGE_BNS${{TAG}}_INJECTIONS.hdf"
BANK_FILE="{BANKS_BASE_DIR}/{s_id}/merged/FIR_BANK_MERGED_FLAT.hdf"
VETO_FILE="{GLOBAL_VETO_FILE}"
OUT_FILE="${{IFO}}-SNGLS_BNS${{TAG}}_INJECTIONS_1DET_JOB${{PART}}.hdf"

{PYCBC_BIN}/pycbc_sngls_findtrigs \\
    --ranking-statistic exp_fit \\
    --statistic-features phasetd sensitive_volume normalize_fit_rate \\
    --statistic-keywords alpha_below_thresh:6 \\
    --sngl-ranking newsnr_sgveto_psdvar \\
    --randomize-template-order \\
    --template-bank ${{BANK_FILE}} \\
    --trigger-files ${{TRIG_FILE}} \\
    --statistic-files H1-FIT_OVER_PARAM_FULL_DATA.hdf L1-FIT_OVER_PARAM_FULL_DATA.hdf \\
    --veto-files ${{VETO_FILE}} \\
    --segment-name vetoes \\
    --template-fraction-range ${{PART}}/${{NUM_PARTS}} \\
    --output-file ${{OUT_FILE}}
"""
    sh_path = os.path.join(sub_dir, "sngls_inj.sh")
    with open(sh_path, "w") as f:
        f.write(sh_content)
    os.chmod(sh_path, 0o755)

    queue_lines = []
    for tag in tags:
        for ifo in DETECTORS:
            for part in range(NUM_SPLITS):
                queue_lines.append(f"    {ifo}, {tag}, {part}")

    sub_content = f"""universe = vanilla
executable = sngls_inj.sh
arguments = $(ifo) $(tag) $(part) {NUM_SPLITS}
getenv = True

output = logs/sngls_inj_$(tag)_$(ifo)_job$(part).out
error  = logs/sngls_inj_$(tag)_$(ifo)_job$(part).err
log    = logs/sngls_inj_$(tag)_$(ifo)_job$(part).log

request_cpus = 1
request_memory = 16 GB
request_disk = 10 GB

queue ifo,tag,part from (
{chr(10).join(queue_lines)}
)
"""
    with open(os.path.join(sub_dir, "sngls_inj.sub"), "w") as f:
        f.write(sub_content)

def write_sngls_statmap_inj(sub_dir, s_id, tags):
    sh_content = f"""#!/bin/bash
set -e
IFO=$1
TAG=$2

if [ -z "$IFO" ] || [ -z "$TAG" ]; then
    echo "Usage: ./sngls_statmap_inj.sh [H1|L1] [TAG]"
    exit 1
fi

FILES=$(ls ${{IFO}}-SNGLS_BNS${{TAG}}_INJECTIONS_1DET_JOB*.hdf 2>/dev/null)
if [ -z "$FILES" ]; then
    echo "Error: No ${{IFO}}-SNGLS_BNS${{TAG}}_INJECTIONS_1DET_JOB*.hdf files found."
    exit 1
fi

BACKGROUND_FILE="${{IFO}}-SNGLS_STATMAP_FULL_DATA_1DET.hdf"
OUT_FILE="${{IFO}}-SNGLS_STATMAP_INJ_BNS${{TAG}}_INJECTIONS_1DET.hdf"

{PYCBC_BIN}/pycbc_sngls_statmap_inj \\
    --veto-window 0.100 \\
    --cluster-window 10.0 \\
    --far-calculation-method H1:trigger_fit L1:trigger_fit \\
    --fit-function H1:exponential L1:exponential \\
    --fit-threshold H1:15 L1:15 \\
    --sngls-files $FILES \\
    --full-data-background ${{BACKGROUND_FILE}} \\
    --ifos ${{IFO}} \\
    --output-file ${{OUT_FILE}}
"""
    sh_path = os.path.join(sub_dir, "sngls_statmap_inj.sh")
    with open(sh_path, "w") as f:
        f.write(sh_content)
    os.chmod(sh_path, 0o755)

    queue_lines = []
    for tag in tags:
        for ifo in DETECTORS:
            queue_lines.append(f"    {ifo}, {tag}")

    sub_content = f"""universe = vanilla
executable = sngls_statmap_inj.sh
arguments = $(ifo) $(tag)
getenv = True

output = logs/sngls_statmap_inj_$(tag)_$(ifo).out
error  = logs/sngls_statmap_inj_$(tag)_$(ifo).err
log    = logs/sngls_statmap_inj_$(tag)_$(ifo).log

request_cpus = 1
request_memory = 16 GB
request_disk = 10 GB

queue ifo,tag from (
{chr(10).join(queue_lines)}
)
"""
    with open(os.path.join(sub_dir, "sngls_statmap_inj.sub"), "w") as f:
        f.write(sub_content)

def main():
    print("Generating injection singles scripts with GLOBAL_VETOES for sub-searches 1, 3, 9, 20, 26...")
    for s_id, tags in INJECTION_MAPPING.items():
        sub_dir = os.path.join(BASE_SEARCH_DIR, str(s_id))
        os.makedirs(sub_dir, exist_ok=True)
        os.makedirs(os.path.join(sub_dir, "logs"), exist_ok=True)

        write_sngls_inj(sub_dir, s_id, tags)
        write_sngls_statmap_inj(sub_dir, s_id, tags)

        print(f"  [✓] Configured injection singles for Sub-search {s_id:02d} -> {sub_dir}")

    print("\n[✓] All injection files updated with vetoes.")

if __name__ == "__main__":
    main()
