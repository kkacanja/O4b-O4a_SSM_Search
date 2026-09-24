import os
import sys
import shutil
import h5py
import numpy as np
import configparser

# --- Configuration Paths ---
BASE_DIR = "/home/kkacanja/sub-solar-search/O4a"
BANKS_DIR = "/home/kkacanja/sub-solar-search/banks/26sub"
MAIN_CONFIGS_DIR = os.path.join(BASE_DIR, "main_configs")
TIMES_DIR = os.path.join(BASE_DIR, "times")
INJ_CONFIGS_DIR = os.path.join(BASE_DIR, "inj_confgs")
SEARCH_DIR = os.path.join(BASE_DIR, "search")

NUM_SUB_SEARCHES = 26
NUM_TIME_CHUNKS = 41

# List of injection keys and their associated physical mchirp value
INJECTION_MAPPING = {
    "bns0.1": 0.1,
    "bns0.2": 0.2,
    "bns0.35": 0.35,
    "bns0.5": 0.5,
    "bns0.7": 0.7,
    "bns1.1": 1.1,
    "bns1.2": 1.2
}

def get_bank_mchirp_bounds(sub_idx):
    """Opens the flat bank for a sub-search and finds the exact mchirp coverage."""
    bank_path = os.path.join(BANKS_DIR, str(sub_idx), "merged", "FIR_BANK_MERGED_FLAT.hdf")
    if not os.path.exists(bank_path):
        return None, None
    try:
        with h5py.File(bank_path, 'r') as hf:
            mchirps = hf['mchirp'][:]
            # Adding a tiny 1% padding tolerance buffer on bounds
            return np.min(mchirps) * 0.99, np.max(mchirps) * 1.01
    except Exception as e:
        print(f"  [!] Error reading bank {sub_idx}: {e}")
        return None, None

def patch_analysis_ini(sub_idx, src_path, dest_path):
    """Updates bank directory tracking parameters inside the analysis config."""
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(src_path)
    
    # 1. Update Pregenerated bank properties
    if not parser.has_section('workflow-tmpltbank'):
        parser.add_section('workflow-tmpltbank')
    parser.set('workflow-tmpltbank', 'tmpltbank-method', 'PREGENERATED_BANK')
    parser.set('workflow-tmpltbank', 'tmpltbank-pregenerated-bank', 
               f"/home/kkacanja/sub-solar-search/banks/26sub/{sub_idx}/merged/FIR_BANK_MERGED_FLAT.hdf")
    
    # 2. Update split directory parameters
    if not parser.has_section('workflow-splittable'):
        parser.add_section('workflow-splittable')
    parser.set('workflow-splittable', 'splittable-method', 'MANUAL_DIRECTORY')
    
    if not parser.has_section('workflow-splittable-full_data'):
        parser.add_section('workflow-splittable-full_data')
    parser.set('workflow-splittable-full_data', 'tmpltbank-directory', 
               f"/home/kkacanja/sub-solar-search/banks/26sub/{sub_idx}/full_data")
               
    if not parser.has_section('workflow-splittable-injections'):
        parser.add_section('workflow-splittable-injections')
    parser.set('workflow-splittable-injections', 'tmpltbank-directory', 
               f"/home/kkacanja/sub-solar-search/banks/26sub/{sub_idx}/inj")
               
    with open(dest_path, 'w') as f:
        parser.write(f)

def build_custom_time_ini(time_idx, min_mc, max_mc, dest_path):
    """Filters injection config templates so only valid masses are included."""
    # Check if this specific time index has an active injection configuration template
    src_path = os.path.join(INJ_CONFIGS_DIR, f"gps_times_O4a_analysis_{time_idx}.ini")
    
    # Fallback to base execution profile time ini if no injection profile exists for this index
    if not os.path.exists(src_path):
        src_path = os.path.join(TIMES_DIR, f"gps_times_O4a_analysis_{time_idx}.ini")
        if not os.path.exists(src_path):
            return False
        shutil.copy(src_path, dest_path)
        return True

    # Parse and filter injection profiles based on template mass bounds
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(src_path)
    
    # Identify which injection subsets match this bank's mchirp bounds
    for inj_name, inj_mc in INJECTION_MAPPING.items():
        if not (min_mc <= inj_mc <= max_mc):
            # Remove sections to avoid execution failure modes
            sect_wf = f"workflow-injections-{inj_name}"
            sect_inj = f"injections-{inj_name}"
            if parser.has_section(sect_wf):
                parser.remove_section(sect_wf)
            if parser.has_section(sect_inj):
                parser.remove_section(sect_inj)
                
    with open(dest_path, 'w') as f:
        parser.write(f)
    return True

# --- Main Automation Loop ---
if __name__ == "__main__":
    print("Starting generation layout for sub-solar matrix parameters...")
    
    for sub_idx in range(1, NUM_SUB_SEARCHES + 1):
        min_mc, max_mc = get_bank_mchirp_bounds(sub_idx)
        if min_mc is None:
            print(f"Skipping Sub-Search {sub_idx}: Flat bank file missing.")
            continue
            
        print(f"\n[+] Configuring Sub-Search Run Folder: {sub_idx} (Mchirp Footprint: {min_mc:.3f} - {max_mc:.3f})")
        
        # Build local target subdirectory layout
        sub_search_base = os.path.join(SEARCH_DIR, str(sub_idx))
        sub_configs_dir = os.path.join(sub_search_base, "main_configs")
        sub_times_dir = os.path.join(sub_search_base, "times")
        
        os.makedirs(sub_configs_dir, exist_ok=True)
        os.makedirs(sub_times_dir, exist_ok=True)
        
        # 1. Duplicate standard immutable configuration scripts
        shutil.copy(os.path.join(MAIN_CONFIGS_DIR, "executables.ini"), sub_configs_dir)
        shutil.copy(os.path.join(MAIN_CONFIGS_DIR, "plotting.ini"), sub_configs_dir)
        
        # 2. Patch the custom analysis options for this specific sub bank pathing setup
        patch_analysis_ini(
            sub_idx, 
            os.path.join(MAIN_CONFIGS_DIR, "analysis.ini"), 
            os.path.join(sub_configs_dir, "analysis.ini")
        )
        
        # 3. Loop over all execution times
        for time_idx in range(NUM_TIME_CHUNKS):
            wf_dir_name = f"O4a{time_idx}"
            wf_run_path = os.path.join(sub_search_base, wf_dir_name)
            os.makedirs(wf_run_path, exist_ok=True)
            
            # Generate custom localized time/injection tracking parameter profile
            local_time_ini = os.path.join(sub_times_dir, f"gps_times_O4a_analysis_{time_idx}.ini")
            success = build_custom_time_ini(time_idx, min_mc, max_mc, local_time_ini)
            if not success:
                continue
                
            # Create the custom launch runner wrapper shell script
            submit_script_path = os.path.join(wf_run_path, "submit.sh")
            with open(submit_script_path, 'w') as sf:
                sf.write(f"""#!/bin/bash
set -e

pycbc_make_offline_search_workflow \\
--workflow-name {wf_dir_name} \\
--output-dir output \\
--config-files ../main_configs/analysis.ini ../main_configs/plotting.ini ../main_configs/executables.ini ../times/gps_times_O4a_analysis_{time_idx}.ini \\
--config-overrides results_page:output-path:/home/kkacanja/public_html/sub-solar-search/O4a/sub{sub_idx}/{wf_dir_name} \\
--submit-now
""")
            # Grant execution privileges directly to shell wrapper
            os.chmod(submit_script_path, 0o755)
            
    print("\n[✔] Setup mapping successfully built across all workspace execution points.")
