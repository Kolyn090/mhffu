clear
# For testing convenience
monster_num="06"
pmo_file="../export/extract/emmodel/em$monster_num-0001.pac"
tmh_file="../export/extract/emmodel/em$monster_num-0002.pac"
material_folder="../export/tmh/emmodel/em$monster_num-0002/"
output_file="../export/test/em$monster_num-0001.obj"

output_folder="../export/test/"

echo "Cleaning up output folder..."
[ -n "$output_folder" ] && rm -rf "$output_folder"/* "$output_folder"/.[!.]* "$output_folder"/..?*
mkdir -p "$output_folder"

echo "Creating texture folder..."
mkdir -p "$output_folder"/texture

echo "Copying mtl file..."
file=$(find "$material_folder" -type f -name '*mtl' -print -quit)
if [ -n "$file" ]; then
    cp "$file" "$output_folder"
else
    echo "No .mtl file found"
fi

echo "Copying textures..."
shopt -s nullglob
files=("$material_folder"/*.png)
[ ${#files[@]} -gt 0 ] && cp "${files[@]}" "$output_folder"/texture

# python3 ../pmo_process/pmo_new.py "$pmo_file" "$tmh_file" "$output_file" --enforce_ge_verbose
python3 ../pmo_process/pmo_new.py "$pmo_file" "$tmh_file" "$output_file" --verbose
