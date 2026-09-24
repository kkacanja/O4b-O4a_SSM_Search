#!/bin/bash

python search_by_hand.py
python search_inj_by_hand.py
python create_exclude_zerolag.py
python combine_stat_hdfinj.py

python make_dag.py

#condor_submit_dag workflow.dag
