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

需要本机安装 JDK 和 Android SDK 后执行：

```powershell
npm.cmd run android
```
