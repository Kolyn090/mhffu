clear

pmo_file="../export/extract/emmodel/em01-0001.pac"
tmh_file="../export/extract/emmodel/em01-0002.pac"
outputfile="../export/test/test.obj"

python3 ../pmo_process/pmo_new.py "$pmo_file" "$tmh_file" "$outputfile" --enforce_ge_verbose
