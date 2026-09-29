param(
  [Parameter(Mandatory = $true)][string]$RimeUserDir,
  [int]$Port = 8765,
  [switch]$DebugText
)
$ErrorActionPreference = 'Stop'
$KaomojiProject = Split-Path -Parent $PSScriptRoot
$KaomojiPython = Join-Path $KaomojiProject '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $KaomojiPython)) {
  $KaomojiPython = (Get-Command python -ErrorAction Stop).Source
}
$KaomojiArguments = @((Join-Path $KaomojiProject 'python\server.py'), '--port', "$Port", '--ipc-dir', (Join-Path $RimeUserDir 'kaomoji_ipc'))
if ($DebugText) { $KaomojiArguments += '--debug-text' }
& $KaomojiPython @KaomojiArguments
