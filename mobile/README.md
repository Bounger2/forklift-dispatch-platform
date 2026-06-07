# 叉车调度移动端

这是独立于 Web 前端的 Expo/React Native 安卓应用，目录为 `mobile`，不会影响原有 `frontend`。

## 后端地址

安卓模拟器访问本机 Flask 后端时默认使用：

```text
http://10.0.2.2:5000
```

真机调试时请改成电脑局域网 IP：

```powershell
$env:EXPO_PUBLIC_API_BASE="http://你的电脑IP:5000"
npm.cmd run start
```

## 启动

```powershell
cd mobile
npm.cmd install
npm.cmd run start
```

## 打包/运行安卓

已准备便携环境目录：

```text
E:\Project program\企业项目\无人调度车\android-env
```

首次安装 Android SDK 组件时需要你本人接受 Google Android SDK License：

```powershell
.\scripts\install-android-sdk.ps1
```

如果 SDK/NDK 下载较慢，并且本机代理为 `127.0.0.1:7890`：

```powershell
.\scripts\install-android-sdk.ps1 -UseProxy
```

脚本会安装 Expo SDK 54 当前需要的 Android 36、Build Tools 36 和 NDK 27.1。

验证移动端依赖和 Android Bundle：

```powershell
.\scripts\doctor.ps1
```

构建本地 debug APK：

```powershell
.\scripts\build-debug-apk.ps1
```

如果 Maven/Gradle 依赖下载仍然慢，并且本机代理为 `127.0.0.1:7890`：

```powershell
.\scripts\build-debug-apk.ps1 -UseProxy
```

项目路径包含中文时，脚本会自动复制到短英文临时目录完成原生构建，避免 CMake/NDK 路径编码问题。构建成功后 APK 会导出到：

```text
mobile\apk\forklift-dispatch-debug.apk
```

连接安卓模拟器或真机后运行：

```powershell
.\scripts\run-android.ps1
```

如果使用真机调试，请将后端地址设置为电脑局域网 IP：

```powershell
$env:EXPO_PUBLIC_API_BASE="http://你的电脑IP:5000"
.\scripts\run-android.ps1
```
