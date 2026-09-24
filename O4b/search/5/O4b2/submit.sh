#!/bin/bash
set -e

pycbc_make_offline_search_workflow \
--workflow-name O4b2 \
--output-dir output \
--config-files ../main_configs/analysis.ini ../main_configs/plotting.ini ../main_configs/executables.ini ../times/gps_times_O4b_analysis_2.ini \
--config-overrides results_page:output-path:/home/kkacanja/public_html/sub-solar-search/O4b/sub5/O4b2 \
--submit-now
