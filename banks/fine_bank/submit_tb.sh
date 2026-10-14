#!/bin/bash

source /home/kkacanja/miniconda3/etc/profile.d/conda.sh
conda activate o4asearch

set -e

start_time=$(date +%s)

echo "Start time: ${start_time} "

pycbc_brute_bank \
--input-config /home/kkacanja/lowmass_search/bank/main_config_1.ini \
--output-file /home/kkacanja/lowmass_search/banks/fixed_l_25hz/360.0-380.0.hdf \
--approximant TaylorF2 \
--psd-file /home/kkacanja/lowmass_search/banks/psds/l1_psd.txt \
--low-frequency-cutoff 20.0 \
--max-signal-length 512 \
--tau0-crawl 5 \
--tau0-start 360.0 \
--tau0-end 365.0 \
--tau0-threshold 0.5 \
--minimal-match 0.95 \
--sample-rate 1048 \
--tolerance 0.001 \
--verbose

end_time=$(date +%s)

echo "End time: ${end_time}"

elapsed_time=$((end_time - start_time))

echo "Script completed in ${elapsed_time} seconds."
