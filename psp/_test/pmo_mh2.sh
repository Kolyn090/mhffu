clear
pmo_file="../export/extract/emmodel/em03-0001.pac"
tmh_file="../export/extract/emmodel/em03-0002.pac"
outputfile="../export/test/em03-0001.obj"
# python3 ../pmo_process/pmo_new.py "$pmo_file" "$tmh_file" "$outputfile" --enforce_ge_verbose
python3 ../pmo_process/pmo_new.py "$pmo_file" "$tmh_file" "$outputfile" --verbose
