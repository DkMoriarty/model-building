# Spark Studio setup for Windows (PowerShell).
#   Right-click > Run with PowerShell, or:  powershell -ExecutionPolicy Bypass -File setup.ps1
# Installs what is missing (via winget), the project's packages, builds every
# episode's soundtrack, and checks the machine with `npm run doctor`.
$ErrorActionPreference = 'Stop'
Set-Location -Path (Join-Path $PSScriptRoot 'alan_pipeline')

function Have($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Need($cmd, $wingetId, $what) {
  if (Have $cmd) { Write-Host "  ok  $what"; return }
  Write-Host "  ..  installing $what ($wingetId)"
  winget install --id $wingetId -e --accept-source-agreements --accept-package-agreements
  $env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path', 'User')
  if (-not (Have $cmd)) { throw "$what installed - close this window, open a new one and run setup.ps1 again." }
}

Write-Host "`nSpark Studio setup`n"
Need 'node' 'OpenJS.NodeJS.LTS' 'Node.js (>= 18.18)'
Need 'python' 'Python.Python.3.12' 'Python 3'
Need 'ffmpeg' 'Gyan.FFmpeg' 'ffmpeg'
if (-not (Test-Path "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe") -and -not (Test-Path "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe")) {
  Write-Host '  !!  No Chrome or Edge found: renders need one (Edge ships with Windows).'
}

Write-Host "`nInstalling packages..."
npm ci
python -m pip install --upgrade pip | Out-Null
python -m pip install numpy

Write-Host "`nBuilding soundtracks..."
python tools/build_space_audio.py --episode first_game
python tools/build_space_audio.py --episode first_light
python tools/build_space_audio.py

Write-Host "`nChecking the machine..."
npm run doctor

Write-Host "`nDone. Try:"
Write-Host '  cd alan_pipeline'
Write-Host '  npm start                      # live editor in the browser'
Write-Host '  npm run render:game            # render FIRST GAME to output_renders/first_game.mp4'
