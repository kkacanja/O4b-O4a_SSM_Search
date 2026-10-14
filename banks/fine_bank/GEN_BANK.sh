#!/bin/bash


#  1. LAMBDA CUTOFF: Value to use for the maximum lambda constraint (e.g., 6e6 or 1e5)
LAMBDA_CUTOFF="7e5"

F_FINAL="800"
SAMPLE_RATE="2048"

#  2. PREFIX updated to use the LAMBDA_CUTOFF variable
prefix="${LAMBDA_CUTOFF}_lam_${F_FINAL}hz_${SAMPLE_RATE}_constraints"

base_dir="runs/"
mkdir -p "$base_dir/${prefix}/sh/"
mkdir -p "$base_dir/${prefix}/sub/"
mkdir -p "$base_dir/${prefix}/banks/"
mkdir -p "$base_dir/${prefix}/logs/"
mkdir -p "$base_dir/${prefix}/ini/"

sh_directory="$base_dir/${prefix}/sh"
sub_directory="$base_dir/${prefix}/sub"
ini_directory="$base_dir/${prefix}/ini"
log_directory="$base_dir/${prefix}/logs"
bank_directory="$base_dir/${prefix}/banks"


# --- Tau0 range ---
q_file="tau0_q_bins.txt"  # precomputed file with lines: tau0_min tau0_max q_min q_max

echo "Starting job generation using precomputed q bins from $q_file"

# --- Loop through tau0 bins using precomputed q values ---
while read tau0_min tau0_max q_min q_max; do
    echo "Processing tau0 bin [$tau0_min, $tau0_max] with q=[${q_min},${q_max}]"

    # --- 1. Create and update INI file ---
    ini_filename="config_${tau0_min}-${tau0_max}.ini"
    ini_file_path="$ini_directory/$ini_filename"
    cp main_config.ini "$ini_file_path"

    # Update tau0/q priors
    sed -i "s/min-tau0 = [0-9.]*/min-tau0 = $tau0_min/" "$ini_file_path"
    sed -i "s/max-tau0 = [0-9.]*/max-tau0 = $tau0_max/" "$ini_file_path"
    sed -i "s/min-q = [0-9.]*/min-q = $q_min/" "$ini_file_path"
    sed -i "s/max-q = [0-9.]*/max-q = $q_max/" "$ini_file_path"

    # Update f_final in INI file
    sed -i "s/^f_final = .*$/f_final = ${F_FINAL}/" "$ini_file_path"

    # This assumes '6e6' is only used for the lambda cutoff in the INI file.
    sed -i "s/6e6/${LAMBDA_CUTOFF}/g" "$ini_file_path"

    # --- 2. Create SH script ---
    sh_filename="submit_tb_${tau0_min}-${tau0_max}.sh"
    sh_file_path="$sh_directory/$sh_filename"
    cp submit_tb.sh "$sh_file_path"
    sed -i "s|--input-config .*|--input-config $ini_file_path \\\\|" "$sh_file_path"
    sed -i "s/--tau0-start [0-9.]*/--tau0-start $tau0_min/" "$sh_file_path"
    sed -i "s/--tau0-end [0-9.]*/--tau0-end $tau0_max/" "$sh_file_path"
    sed -i "s|--output-file .*|--output-file $bank_directory/${tau0_min}-${tau0_max}.hdf \\\\|" "$sh_file_path"

    # Update sample-rate in SH script
    sed -i "s/--sample-rate [0-9]*/--sample-rate ${SAMPLE_RATE}/" "$sh_file_path"

    # --- 3. Create SUB script ---
    sub_filename="submit_tb_${tau0_min}-${tau0_max}.sub"
    sub_file_path="$sub_directory/$sub_filename"
    cp submit_tb.sub "$sub_file_path"

    # Update paths
    sed -i "s|executable = .*|executable = $sh_file_path|" "$sub_file_path"
    sed -i "s|error = .*|error = $log_directory/${tau0_min}-${tau0_max}.err|" "$sub_file_path"
    sed -i "s|output = .*|output = $log_directory/${tau0_min}-${tau0_max}.out|" "$sub_file_path"
    sed -i "s|log = .*|log = $log_directory/${tau0_min}-${tau0_max}.log|" "$sub_file_path"
    sed -i "s/stream_output = .*$/stream_output = True/" "$sub_file_path"
    sed -i "s/stream_error = .*$/stream_error = True/" "$sub_file_path"

    # Update batch_name in SUB script
    sed -i "s/^batch_name = .*$/batch_name = ${prefix}/" "$sub_file_path"

    # --- 4. Submit job ---
    condor_submit "$sub_file_path"
done < "$q_file"

echo "All jobs submitted successfully."
