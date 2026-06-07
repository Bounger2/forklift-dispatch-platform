param(
  [string]$EnvRoot = "",
  [string]$TempBuildRoot = "",
  [switch]$UseProxy,
  [switch]$NoAsciiDrive
)

$ErrorActionPreference = "Stop"

function Set-KotlinSettingsMirrors {
  param([string]$SettingsFile)

  if (-not (Test-Path $SettingsFile)) {
    return
  }

  $content = Get-Content -LiteralPath $SettingsFile -Raw -Encoding UTF8
  if ($content.Contains("maven.aliyun.com/repository/gradle-plugin")) {
    return
  }

  $newline = if ($content.Contains("`r`n")) { "`r`n" } else { "`n" }
  $marker = "  repositories {$newline"
  $mirrors = @(
    '    maven { url = uri("https://maven.aliyun.com/repository/google") }',
    '    maven { url = uri("https://maven.aliyun.com/repository/central") }',
    '    maven { url = uri("https://maven.aliyun.com/repository/gradle-plugin") }'
  ) -join $newline

  $updated = $content.Replace($marker, "$marker$mirrors$newline")
  if ($updated -ne $content) {
    Set-Content -LiteralPath $SettingsFile -Value $updated -Encoding UTF8
  }
}

function New-SubstDrive {
  param(
    [string[]]$Candidates,
    [string]$Target
  )

  foreach ($name in $Candidates) {
    $drive = "${name}:"
    if (-not (Test-Path "${drive}\")) {
      & "$env:SystemRoot\System32\subst.exe" $drive $Target
      return $drive
    }
  }

  throw "No available drive letter for subst mapping."
}

$originalMobileRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$originalMobileParent = (Split-Path $originalMobileRoot -Parent)
$mobileFolderName = Split-Path $originalMobileRoot -Leaf
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
if (-not $EnvRoot) {
  $EnvRoot = Join-Path $repoRoot "android-env"
}
$originalEnvRoot = (Resolve-Path $EnvRoot).Path
$needsAsciiDrive = -not $NoAsciiDrive -and (($originalMobileRoot -match '[^\x00-\x7F]') -or ($originalEnvRoot -match '[^\x00-\x7F]'))

$envDrive = $null
$mobileRoot = $originalMobileRoot
$effectiveEnvRoot = $originalEnvRoot
$tempParent = $null
$buildSucceeded = $false

try {
  if ($needsAsciiDrive) {
    if (-not $TempBuildRoot) {
      $TempBuildRoot = Join-Path $env:USERPROFILE "fdapk-build"
    }
    $stamp = Get-Date -Format "yyyyMMddHHmmss"
    $tempParent = Join-Path $TempBuildRoot $stamp
    $mobileRoot = Join-Path $tempParent $mobileFolderName
    New-Item -ItemType Directory -Force $mobileRoot | Out-Null
    Write-Host "Copying mobile project to ASCII temp path: $mobileRoot"
    & "$env:SystemRoot\System32\robocopy.exe" $originalMobileRoot $mobileRoot /E /MT:8 /R:2 /W:2 /XD ".expo" "dist-android" "apk" "android\.gradle" "android\build" /XF "*.log" /NFL /NDL /NJH /NJS /NP
    if ($LASTEXITCODE -gt 7) {
      throw "robocopy failed with exit code $LASTEXITCODE"
    }

    $envDrive = New-SubstDrive -Candidates @("Y", "T", "S", "R") -Target $originalEnvRoot
    $effectiveEnvRoot = "${envDrive}\"
    Write-Host "Using ASCII build paths: mobile=$mobileRoot env=$effectiveEnvRoot"
  }

  . (Join-Path $PSScriptRoot "env.android.ps1") -EnvRoot $effectiveEnvRoot | Out-Null

  $gradleHome = Join-Path $effectiveEnvRoot "gradle\gradle-8.14.3"
  $gradleBin = Join-Path $gradleHome "bin\gradle.bat"
  if (-not (Test-Path $gradleBin)) {
    throw "Gradle not found: $gradleBin"
  }

  $env:EXPO_NO_TELEMETRY = "1"
  if (-not $env:NODE_ENV) {
    $env:NODE_ENV = "production"
  }
  $encodingOpts = "-Dfile.encoding=UTF-8 -Dsun.jnu.encoding=UTF-8"
  if ($UseProxy) {
    $env:GRADLE_OPTS = "$encodingOpts -Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7890 -Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=7890"
  } else {
    $env:GRADLE_OPTS = $encodingOpts
  }

  Set-KotlinSettingsMirrors (Join-Path $mobileRoot "node_modules\@react-native\gradle-plugin\settings.gradle.kts")
  Set-KotlinSettingsMirrors (Join-Path $mobileRoot "node_modules\expo-modules-autolinking\android\expo-gradle-plugin\settings.gradle.kts")

  Push-Location (Join-Path $mobileRoot "android")
  try {
    & $gradleBin --no-daemon --console plain :app:assembleDebug
    if ($LASTEXITCODE -ne 0) {
      throw "Gradle failed with exit code $LASTEXITCODE"
    }
  } finally {
    Pop-Location
  }

  $apkSource = Join-Path $mobileRoot "android\app\build\outputs\apk\debug\app-debug.apk"
  if (-not (Test-Path $apkSource)) {
    throw "APK not found after build: $apkSource"
  }

  $apkDir = Join-Path $originalMobileRoot "apk"
  New-Item -ItemType Directory -Force $apkDir | Out-Null
  $apkOutput = Join-Path $apkDir "forklift-dispatch-debug.apk"
  Copy-Item -LiteralPath $apkSource -Destination $apkOutput -Force
  Write-Host "APK exported: $apkOutput"
  $buildSucceeded = $true
} finally {
  if ($envDrive) {
    & "$env:SystemRoot\System32\subst.exe" $envDrive /D
  }
  if ($buildSucceeded -and $tempParent) {
    $tempRoot = (Resolve-Path $TempBuildRoot).Path
    $resolvedTempParent = (Resolve-Path $tempParent).Path
    if ($resolvedTempParent.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
      Remove-Item -LiteralPath $resolvedTempParent -Recurse -Force
    }
  }
}
