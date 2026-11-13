# rehydrate for Windows PowerShell: thin wrapper over tools/rehydrate.sh.
# The logic lives ONLY in the .sh (one implementation). This just finds the
# bash that ships with Git for Windows (not on PATH by default) and runs it.
#
#   powershell -File tools\rehydrate.ps1             # with git fetch
#   powershell -File tools\rehydrate.ps1 --no-fetch  # offline
#
# ASCII-only on purpose: Windows PowerShell 5.1 reads BOM-less .ps1 as ANSI.

$ErrorActionPreference = 'Stop'

$git = (Get-Command git -ErrorAction SilentlyContinue).Source
if (-not $git) { Write-Error 'git not found - install Git for Windows'; exit 1 }

# ...\Git\cmd\git.exe -> ...\Git\bin\bash.exe (fallback: ...\Git\usr\bin\bash.exe)
$gitRoot = Split-Path (Split-Path $git -Parent) -Parent
$bash = @("$gitRoot\bin\bash.exe", "$gitRoot\usr\bin\bash.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $bash) { Write-Error "Git Bash not found under $gitRoot"; exit 1 }

# The script prints Cyrillic as UTF-8; make the console decode it as such.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$script = Join-Path $PSScriptRoot 'rehydrate.sh'
& $bash $script @args
exit $LASTEXITCODE
