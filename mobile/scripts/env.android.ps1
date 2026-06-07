param(
  [string]$EnvRoot = ""
)

$ErrorActionPreference = "Stop"

if (-not $EnvRoot) {
  $repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
  $EnvRoot = Join-Path $repoRoot "android-env"
}

$jdkRoot = Join-Path $EnvRoot "jdk"
$sdkRoot = Join-Path $EnvRoot "android-sdk"
$cmdlineTools = Join-Path $sdkRoot "cmdline-tools\latest"

if (-not (Test-Path $jdkRoot)) {
  throw "JDK directory not found: $jdkRoot"
}

$jdkHome = (Get-ChildItem $jdkRoot -Directory | Sort-Object Name | Select-Object -First 1).FullName
if (-not $jdkHome) {
  throw "No JDK found under: $jdkRoot"
}

if (-not (Test-Path (Join-Path $jdkHome "bin\java.exe"))) {
  throw "java.exe not found under: $jdkHome"
}

$env:JAVA_HOME = $jdkHome
$env:ANDROID_HOME = $sdkRoot
$env:ANDROID_SDK_ROOT = $sdkRoot
$env:PATH = "$jdkHome\bin;$cmdlineTools\bin;$sdkRoot\platform-tools;$env:PATH"

[pscustomobject]@{
  JAVA_HOME = $env:JAVA_HOME
  ANDROID_SDK_ROOT = $env:ANDROID_SDK_ROOT
}
