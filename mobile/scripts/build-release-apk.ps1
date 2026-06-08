param(
  [string]$EnvRoot = "",
  [string]$TempBuildRoot = "",
  [switch]$UseProxy,
  [switch]$NoAsciiDrive
)

$argsForBuild = @{
  BuildType = "Release"
}

if ($EnvRoot) {
  $argsForBuild.EnvRoot = $EnvRoot
}
if ($TempBuildRoot) {
  $argsForBuild.TempBuildRoot = $TempBuildRoot
}
if ($UseProxy) {
  $argsForBuild.UseProxy = $true
}
if ($NoAsciiDrive) {
  $argsForBuild.NoAsciiDrive = $true
}

& (Join-Path $PSScriptRoot "build-debug-apk.ps1") @argsForBuild
