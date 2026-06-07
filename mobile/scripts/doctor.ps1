param(
  [string]$EnvRoot = ""
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "env.android.ps1") -EnvRoot $EnvRoot | Out-Null

$env:EXPO_NO_TELEMETRY = "1"
npm.cmd run doctor
npx.cmd expo export --platform android --output-dir dist-android
