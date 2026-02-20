$src  = 'C:\Fusion Gadgets\SpaceMouseDrawingMode\SpaceMouseDrawingMode.bundle\Contents'
$zip  = 'C:\Fusion Gadgets\SpaceMouseDrawingMode\dist\addin.zip'
$b64f = 'C:\Fusion Gadgets\SpaceMouseDrawingMode\dist\addin.b64'
$tmp  = "C:\Temp\SMBuild_$([guid]::NewGuid().ToString('N').Substring(0,8))"
$dest = Join-Path $tmp 'SpaceMouseDrawingMode'

New-Item -ItemType Directory -Path $dest -Force | Out-Null
Copy-Item (Join-Path $src '*') $dest -Recurse -Force

if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path $dest -DestinationPath $zip -Force
Remove-Item $tmp -Recurse -Force

$bytes = [System.IO.File]::ReadAllBytes($zip)
$b64   = [Convert]::ToBase64String($bytes)
[System.IO.File]::WriteAllText($b64f, $b64)

Write-Host "ZIP size  : $($bytes.Length) bytes"
Write-Host "B64 length: $($b64.Length) chars"
Write-Host "Done."
