param(
  [string]$EnvRoot = ""
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "env.android.ps1") -EnvRoot $EnvRoot | Out-Null

$sdkManager = Join-Path $env:ANDROID_SDK_ROOT "cmdline-tools\latest\bin\sdkmanager.bat"
if (-not (Test-Path $sdkManager)) {
  throw "sdkmanager not found: $sdkManager"
}

Write-Host "JAVA_HOME=$env:JAVA_HOME"
Write-Host "ANDROID_SDK_ROOT=$env:ANDROID_SDK_ROOT"
Write-Host ""
Write-Host "This step installs Android SDK components and requires accepting the Google Android SDK License."
Write-Host "If you accept the license terms shown by sdkmanager, type y when prompted."
Write-Host ""

& $sdkManager "platform-tools" "platforms;android-35" "build-tools;35.0.0"

Write-Host ""
Write-Host "Android SDK install finished."
