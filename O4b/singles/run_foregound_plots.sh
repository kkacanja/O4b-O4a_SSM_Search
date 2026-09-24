#exclude=(1 3 9 20 26)
exclude=(27)
outdir=~/public_html/sub-solar-search/O4b/SINGLES/search/
mkdir -p "$outdir"

for d in */; do
    d_name=${d%/}
    # Skip excluded folders
    [[ " ${exclude[@]} " =~ " ${d_name} " ]] && continue
    
    # Copy & run exclude_zerolag.sh if present in folder 1
    if [[ -f "1/exclude_zerolag.sh" ]] && [[ -d "$d" ]]; then
        cp 1/exclude_zerolag.sh "$d/"
        (cd "$d" && ./exclude_zerolag.sh)
        echo "[✓] Ran exclude_zerolag.sh in $d_name"
    fi
    
    # Plot H1 if H1 exclude file exists
    if [[ -f "$d/H1-EXCLUDE_ZEROLAG_FULL_DATA_1DET.hdf" ]]; then
        /home/kkacanja/miniconda3/envs/fir/bin/pycbc_page_ifar \
            --decimation-factor 100 --open-box \
            --trigger-file "$d/H1-EXCLUDE_ZEROLAG_FULL_DATA_1DET.hdf" \
            --output-file "$outdir/H1-PAGE_IFAR_FULL_DATA_1DET_OPEN_BOX_${d_name}.png"
    fi
    
    # Plot L1 if L1 exclude file exists
    if [[ -f "$d/L1-EXCLUDE_ZEROLAG_FULL_DATA_1DET.hdf" ]]; then
        /home/kkacanja/miniconda3/envs/fir/bin/pycbc_page_ifar \
            --decimation-factor 100 --open-box \
            --trigger-file "$d/L1-EXCLUDE_ZEROLAG_FULL_DATA_1DET.hdf" \
            --output-file "$outdir/L1-PAGE_IFAR_FULL_DATA_1DET_OPEN_BOX_${d_name}.png"
    fi
    echo "[✓] Plotted $d_name"
done
