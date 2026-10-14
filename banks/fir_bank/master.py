import os
import glob
import re 
import sys
import argparse # Not used here, but good practice to keep import if future changes need it

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Calculate ABSOLUTE paths for input data
PARENT_DIR = os.path.dirname(BASE_DIR)

# Absolute Paths to the data folders
COARSE_DIR_ABS = os.path.join(PARENT_DIR, 'COARSE_EOS')
FINE_DIR_ABS = os.path.join(PARENT_DIR, 'FINE_EOS')
F_LOW_MAP_FILE_ABS = os.path.join(COARSE_DIR_ABS, 'flower.txt')

# Output subdirectories
SH_DIR = '/home/kkacanja/lowmass_search/fir/FIR_EOS/sh'
SUB_DIR = '/home/kkacanja/lowmass_search/fir/FIR_EOS/sub'
LOGS_DIR = '/home/kkacanja/lowmass_search/fir/FIR_EOS/logs'

# Constants
PSD_FILE = '/home/kkacanja/GW250114/pe/psds/l1_psd.txt'
CONDA_ACTIVATE_CMD = 'source /home/kkacanja/miniconda3/etc/profile.d/conda.sh; conda activate fir'

# Find all unique bank indices and their names
# We use the ABSOLUTE path to glob the files
bank_files = sorted(glob.glob(os.path.join(COARSE_DIR_ABS, 'COARSE_BANK_*.hdf')))
NUM_JOBS = len(bank_files)
print(f"Detected {NUM_JOBS} bank files (Jobs 0 to {NUM_JOBS - 1}).")


# --- 1. Read f-low data into a dictionary ---
f_low_data = {}
F_LOW_LINE_REGEX = re.compile(r'COARSE_BANK_(\d+)_.*?:\s*([\d\.]+) Hz')

try:
    with open(F_LOW_MAP_FILE_ABS, 'r') as f:
        lines = f.readlines()
    for line in lines:
        match = F_LOW_LINE_REGEX.search(line)
        if match:
            bank_index = int(match.group(1))
            f_low_value = float(match.group(2))
            f_low_data[bank_index] = f_low_value
except FileNotFoundError:
    print(f"CRITICAL ERROR: F-low map file not found at {F_LOW_MAP_FILE_ABS}. Aborting.")
    sys.exit(1)

if len(f_low_data) != NUM_JOBS:
    print(f"Warning: F-low map contains {len(f_low_data)} entries, expected {NUM_JOBS}. Proceeding with available data.")


# --- 2. Define COMMON_ARGS (No static f-low) ---
COMMON_ARGS = """
    --psd-file {psd_file} \\
    --approximant TaylorF2 \\
    --sample-rate 2048 \\
    --n-taps 51 \\
    --max-taps 2001 \\
    --tap-step 100 \\
    --min-match 0.99999 \\
    --delta-f .25 \\
    --n-processes 4 \\
    --verbose
""".format(psd_file=PSD_FILE).strip()


# --- 3. Generate Individual Files ---
os.makedirs(SH_DIR, exist_ok=True)
os.makedirs(SUB_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

master_submit_content = ""
job_count = 0

print("\n--- Generating Individual Job Files ---")

for job_index in range(NUM_JOBS):
    if job_index not in f_low_data:
        print(f"Skipping job {job_index}: f-low value missing from map.")
        continue
        
    bank_filename = os.path.basename(bank_files[job_index])
    f_low_value = f_low_data[job_index]
    
    # Derive output names
    output_name = bank_filename.replace('COARSE_BANK', 'FIR_BANK').replace('_flowfixed', '')
    job_identifier = f"bank_{job_index:03d}" 
    
    # --- 3a. Generate Shell Script (.sh) ---
    sh_filename = f"{job_identifier}.sh"
    sh_filepath = os.path.join(SH_DIR, sh_filename)
    
    sh_content = f"""#!/bin/bash
# Dedicated FIR Bank Job: {job_identifier}

{CONDA_ACTIVATE_CMD}

export NUMEXPR_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export TF_NUM_THREADS=1
export JULIA_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OMP_NUM_THREADS=1

BANK_NAME="{bank_filename}"
F_LOW_VALUE="{f_low_value}"
OUTPUT_NAME="{output_name}"

echo "Starting job {job_index} for bank: ${{BANK_NAME}} with F_LOW=${{F_LOW_VALUE}} Hz"

# --- Execute the pycbc_fir_bank command using ABSOLUTE PATHS ---
pycbc_fir_bank \\
    --coarse-bank {COARSE_DIR_ABS}/${{BANK_NAME}} \\
    --fine-bank {FINE_DIR_ABS}/${{BANK_NAME/COARSE_BANK/FINE_BANK}} \\
    --output-file /home/kkacanja/lowmass_search/fir/FIR_EOS/banks/${{OUTPUT_NAME}} \\
    --f-low ${{F_LOW_VALUE}} \\
    {COMMON_ARGS}

EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "ERROR: pycbc_fir_bank failed with exit code $EXIT_CODE." 1>&2
    exit $EXIT_CODE
fi

if [ ! -f "/home/kkacanja/lowmass_search/fir/FIR_EOS/banks/${{OUTPUT_NAME}}" ]; then
    echo "CRITICAL ERROR: pycbc_fir_bank completed (Code 0), but output file ${{OUTPUT_NAME}} was NOT created." 1>&2
    exit 1
fi

echo "Job {job_index} finished successfully."
"""
    with open(sh_filepath, 'w') as f:
        f.write(sh_content)
    os.chmod(sh_filepath, 0o755)

    # --- 3b. Generate Condor Submission File (.sub) ---
    sub_filename = f"{job_identifier}.sub"
    sub_filepath = os.path.join(SUB_DIR, sub_filename)
    
    # NOTE: Executable path must be relative to the submit directory!
    sub_content = f"""
# Condor Submission File for {job_identifier}

Universe   = vanilla
Executable = {sh_filepath}
Log        = {LOGS_DIR}/{job_identifier}.log
Output     = {LOGS_DIR}/{job_identifier}.out
Error      = {LOGS_DIR}/{job_identifier}.err

# Resources (Adjust Request_Memory to a higher value like 16000MB if needed)
Request_Cpus    = 4
Request_Memory  = 60GB
Request_Disk    = 1000MB

batch_name = FIR_BANK_EOS
# Transfer the PSD file (input files listed here are relative to the Executable)
Transfer_Input_Files = {PSD_FILE}

Requirements = TARGET.Arch == "X86_64" && TARGET.OpSys == "LINUX"

Queue 1
"""
    with open(sub_filepath, 'w') as f:
        f.write(sub_content)
        
    # Add to master submit file
    master_submit_content += f"queue 1 process from {sub_filepath}\n"
    job_count += 1
    
# --- 4. Write Master Submission File ---
master_filepath = 'master_fir_submit.sub'
with open(master_filepath, 'w') as f:
    f.write(master_submit_content)
    
print("-" * 40)
print(f"Total Jobs Generated: {job_count}")
print(f"Scripts are in: {SH_DIR}/")
print(f"Submission files are in: {SUB_DIR}/")
print(f"Master submit file: {master_filepath}")
print("-" * 40)
print("1. To test Job 51 locally: ./{SH_DIR}/bank_051.sh")
print("2. To submit all jobs: condor_submit {master_filepath}")
