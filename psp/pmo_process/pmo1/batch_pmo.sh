inputfolder="../export/extract/player/f/arm/"
outputfolder="../export/pmo/player/f/arm/"
echo "Process $inputfolder -> $outputfolder"
python3 batch_pmo.py "$inputfolder" "$outputfolder" --pmo1_code "0000" --mtl1_code "0001"

inputfolder="../export/extract/player/f/body/"
outputfolder="../export/pmo/player/f/body/"
echo "Process $inputfolder -> $outputfolder"
python3 batch_pmo.py "$inputfolder" "$outputfolder" --pmo1_code "0000" --mtl1_code "0001"

inputfolder="../export/extract/player/f/face/"
outputfolder="../export/pmo/player/f/face/"
echo "Process $inputfolder -> $outputfolder"
python3 batch_pmo.py "$inputfolder" "$outputfolder" --pmo1_code "0000" --mtl1_code "0001"

inputfolder="../export/extract/player/f/hair/"
outputfolder="../export/pmo/player/f/hair/"
echo "Process $inputfolder -> $outputfolder"
python3 batch_pmo.py "$inputfolder" "$outputfolder" --pmo1_code "0000" --mtl1_code "0001"

inputfolder="../export/extract/player/f/head/"
outputfolder="../export/pmo/player/f/head/"
echo "Process $inputfolder -> $outputfolder"
python3 batch_pmo.py "$inputfolder" "$outputfolder" --pmo1_code "0000" --mtl1_code "0001"

inputfolder="../export/extract/player/f/reg/"
outputfolder="../export/pmo/player/f/reg/"
echo "Process $inputfolder -> $outputfolder"
python3 batch_pmo.py "$inputfolder" "$outputfolder" --pmo1_code "0000" --mtl1_code "0001"

inputfolder="../export/extract/player/f/wst/"
outputfolder="../export/pmo/player/f/wst/"
echo "Process $inputfolder -> $outputfolder"
python3 batch_pmo.py "$inputfolder" "$outputfolder" --pmo1_code "0000" --mtl1_code "0001"

inputfolder="../export/extract/player/m/arm/"
outputfolder="../export/pmo/player/m/arm/"
echo "Process $inputfolder -> $outputfolder"
python3 batch_pmo.py "$inputfolder" "$outputfolder" --pmo1_code "0000" --mtl1_code "0001"

inputfolder="../export/extract/player/m/body/"
outputfolder="../export/pmo/player/m/body/"
echo "Process $inputfolder -> $outputfolder"
python3 batch_pmo.py "$inputfolder" "$outputfolder" --pmo1_code "0000" --mtl1_code "0001"

inputfolder="../export/extract/player/m/face/"
outputfolder="../export/pmo/player/m/face/"
echo "Process $inputfolder -> $outputfolder"
python3 batch_pmo.py "$inputfolder" "$outputfolder" --pmo1_code "0000" --mtl1_code "0001"

inputfolder="../export/extract/player/m/hair/"
outputfolder="../export/pmo/player/m/hair/"
echo "Process $inputfolder -> $outputfolder"
python3 batch_pmo.py "$inputfolder" "$outputfolder" --pmo1_code "0000" --mtl1_code "0001"

inputfolder="../export/extract/player/m/head/"
outputfolder="../export/pmo/player/m/head/"
echo "Process $inputfolder -> $outputfolder"
python3 batch_pmo.py "$inputfolder" "$outputfolder" --pmo1_code "0000" --mtl1_code "0001"

inputfolder="../export/extract/player/m/reg/"
outputfolder="../export/pmo/player/m/reg/"
echo "Process $inputfolder -> $outputfolder"
python3 batch_pmo.py "$inputfolder" "$outputfolder" --pmo1_code "0000" --mtl1_code "0001"

inputfolder="../export/extract/player/m/wst/"
outputfolder="../export/pmo/player/m/wst/"
echo "Process $inputfolder -> $outputfolder"
python3 batch_pmo.py "$inputfolder" "$outputfolder" --pmo1_code "0000" --mtl1_code "0001"

inputfolder="../export/extract/cat/"
outputfolder="../export/pmo/cat/"
echo "Process $inputfolder -> $outputfolder"
python3 batch_pmo.py "$inputfolder" "$outputfolder" --pmo1_code "0001" --mtl1_code "0002"

inputfolder="../export/extract/edit/"
outputfolder="../export/pmo/edit/"
echo "Process $inputfolder -> $outputfolder"
python3 batch_pmo.py "$inputfolder" "$outputfolder" --pmo1_code "0000" --mtl1_code "0002"

inputfolder="../export/extract/effect/"
outputfolder="../export/pmo/effect/"
echo "Process $inputfolder -> $outputfolder"
python3 batch_pmo.py "$inputfolder" "$outputfolder" --pmo1_code "0001" --mtl1_code "0002" 

inputfolder="../export/extract/emmodel/"
outputfolder="../export/pmo/emmodel/"
echo "Process $inputfolder -> $outputfolder"
python3 batch_pmo.py "$inputfolder" "$outputfolder" --pmo1_code "0001" --mtl1_code "0002" --pmo2_code "0005" --mtl2_code "0006"

inputfolder="../export/extract/npc/"
outputfolder="../export/pmo/npc/"
echo "Process $inputfolder -> $outputfolder"
python3 batch_pmo.py "$inputfolder" "$outputfolder" --pmo1_code "0001" --mtl1_code "0002"

inputfolder="../export/extract/stage/"
outputfolder="../export/pmo/stage/"
echo "Process $inputfolder -> $outputfolder"
python3 batch_pmo.py "$inputfolder" "$outputfolder" --pmo1_code "0000" --mtl1_code "0001" --pmo2_code "0002" --mtl2_code "0001"

inputfolder="../export/extract/weapon/"
outputfolder="../export/pmo/weapon/"
echo "Process $inputfolder -> $outputfolder"
python3 batch_pmo.py "$inputfolder" "$outputfolder" --pmo1_code "0000" --mtl1_code "0002"
