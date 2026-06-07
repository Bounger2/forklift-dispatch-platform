param(
  [string]$EnvRoot = "",
  [switch]$UseProxy
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "env.android.ps1") -EnvRoot $EnvRoot | Out-Null

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$gradleHome = Join-Path $repoRoot "android-env\gradle\gradle-8.14.3"
$gradleBin = Join-Path $gradleHome "bin\gradle.bat"
if (-not (Test-Path $gradleBin)) {
  throw "Gradle not found: $gradleBin"
}

$env:EXPO_NO_TELEMETRY = "1"
$encodingOpts = "-Dfile.encoding=UTF-8 -Dsun.jnu.encoding=UTF-8"
if ($UseProxy) {
  $env:GRADLE_OPTS = "$encodingOpts -Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7890 -Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=7890"
} else {
  $env:GRADLE_OPTS = $encodingOpts
}

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

$mobileRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-KotlinSettingsMirrors (Join-Path $mobileRoot "node_modules\@react-native\gradle-plugin\settings.gradle.kts")
Set-KotlinSettingsMirrors (Join-Path $mobileRoot "node_modules\expo-modules-autolinking\android\expo-gradle-plugin\settings.gradle.kts")

Push-Location (Join-Path $PSScriptRoot "..\android")
try {
  & $gradleBin --no-daemon --console plain :app:assembleDebug
} finally {
  Pop-Location
}
