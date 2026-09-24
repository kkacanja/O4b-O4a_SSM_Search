#!/usr/bin/env python3
import os

base_dir = "."
dag_file = "workflow_inj.dag"

# Target chunks requiring full injection pipelines
INJ_CHUNKS = {"1", "3", "9", "20", "26"}

subdirs = [
    d
    for d in os.listdir(base_dir)
    if os.path.isdir(os.path.join(base_dir, d)) and d.isdigit()
]
subdirs.sort(key=int)

with open(dag_file, "w") as f:
    f.write("# Master DAG configuration\n")
    f.write("CONFIG dagman.config\n\n")

    for chunk in subdirs:
        chunk_dir = os.path.join(base_dir, chunk)

        f.write(f"# =========================================\n")
        f.write(f"# Chunk {chunk}\n")
        f.write(f"# =========================================\n")

        # Core background pipeline jobs
        f.write(f"JOB  fitby_{chunk}             fitby.sub             DIR {chunk}\n")
        f.write(f"JOB  fitover_{chunk}           fitover.sub           DIR {chunk}\n")
        f.write(f"JOB  sngls_{chunk}             sngls.sub             DIR {chunk}\n")
        f.write(f"JOB  statmap_{chunk}           sngls_statmap.sub     DIR {chunk}\n")
        f.write(f"JOB  exclude_zerolag_{chunk}   exclude_zerolag.sub   DIR {chunk}\n")

        run_inj = (chunk in INJ_CHUNKS) and os.path.exists(os.path.join(chunk_dir, "sngls_inj.sub"))

        if run_inj:
            f.write(f"JOB  sngls_inj_{chunk}         sngls_inj.sub         DIR {chunk}\n")
            f.write(f"JOB  statmap_inj_{chunk}       sngls_statmap_inj.sub DIR {chunk}\n")
            f.write(f"JOB  combine_statmap_{chunk}   combine_statmap.sub   DIR {chunk}\n")
            f.write(f"JOB  hdfinjfind_{chunk}        hdfinjfind.sub        DIR {chunk}\n")

        # Dependencies
        f.write(f"PARENT fitby_{chunk} CHILD fitover_{chunk}\n")
        f.write(f"PARENT sngls_{chunk} CHILD statmap_{chunk}\n")
        f.write(f"PARENT statmap_{chunk} CHILD exclude_zerolag_{chunk}\n")

        if run_inj:
            # fitover is needed by both foreground and injection trigs
            f.write(f"PARENT fitover_{chunk} CHILD sngls_{chunk} sngls_inj_{chunk}\n")
            # statmap_inj requires injection trigs + the zero-lag background statmap
            f.write(f"PARENT sngls_inj_{chunk} statmap_{chunk} CHILD statmap_inj_{chunk}\n")
            # combine_statmap needs both single-IFO injection statmaps and exclude_zerolag files
            f.write(f"PARENT statmap_inj_{chunk} exclude_zerolag_{chunk} CHILD combine_statmap_{chunk}\n")
            # hdfinjfind needs combined statmap
            f.write(f"PARENT combine_statmap_{chunk} CHILD hdfinjfind_{chunk}\n")
        else:
            f.write(f"PARENT fitover_{chunk} CHILD sngls_{chunk}\n")

        f.write("\n")

print(f"Generated {dag_file} with target injection chunks: {', '.join(sorted(INJ_CHUNKS, key=int))}")
