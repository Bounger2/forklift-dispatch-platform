# 厂内叉车智能调度平台

本项目根据 `合同与方案/【软件更新】中天科技厂内叉车智能调度系统方案-0526.docx` 落地软件部分：前端 Vue、后端 Flask、数据库 MySQL 兼容，并预留企业微信消息推送与后续硬件 GPS/北斗定位数据接入。

## 已实现模块

- 一个任务池：用车申请、待审核、待派单、执行中、异常、完成全状态台账；发布任务支持固定点位下拉选择，也支持卫星地图临时标点，临时取送点随任务完成自动隐藏。
- 一个调度引擎：先过滤、再评分、后确认，覆盖排班、人车绑定、车辆状态、电量、距离 ETA、优先级、司机负荷、区域拥堵、人工规则。
- 两类角色入口：管理员、叉车司机。管理员拥有全部权限，负责发布任务、自动/手动派单、点位维护、规则库、账号和报表；司机登录后进入司机主页，可上下线、查看个人图表报表、查看空闲叉车位置并申请绑定，也可接受/拒绝/完成任务。
- 企业微信闭环：用户字段含 `wecom_user_id`，消息进入 `wecom_messages`，配置企业微信参数后可真实推送。
- 排班与人车绑定：班次模板、当班安排增删改、RFID/人工绑定记录，未绑定车辆不进候选池。
- 叉车台账：管理员可新增、修改、停用叉车，支持电动、柴油、汽油、液化气等动力类型和电量/油量维护。
- 真实 GPS 定位：总览和调度推荐优先读取 `forklift_positions` 最新定位，支持硬件写入 `x/y`，也支持配置厂区经纬度边界后由 `lat/lng` 映射到左右厂区卫星图。
- GPS 四角标定：管理员可在“取送货点”页面切换“坐标标定”，在厂区边界四角点击标点，地图会自动填入该点经纬度，系统按四角标定关系把硬件 `lat/lng` 换算为地图 `x/y`。
- 卫星底图：地图组件直接加载 Google 卫星瓦片，默认中心为 `31.9438027,120.9854705`，覆盖中天海缆左右两个厂区，并叠加取送货点和叉车实时位置。
- 管理员报表：按周、月、季度统计每个司机的任务数、运送公里数、作业时长。
- 干净流程样例：默认只保留少量样例任务；自动定位模拟默认关闭，页面不再展示手动推进按钮。

## 目录

```text
调度系统/
  backend/                Flask API、调度算法、模拟定位、企业微信服务
  frontend/               Vue 调度台
  database/mysql_schema.sql
```

## 后端运行

```powershell
cd "E:\Project program\企业项目\无人调度车\调度系统\backend"
python -m pip install -r requirements.txt
python run.py reset
python run.py --host 127.0.0.1 --port 5000
```

当前后端已通过 `backend/.env` 切换为 MySQL 存储，默认连接串为：

```env
DATABASE_URL=mysql+pymysql://dispatch_user:dispatch_password@127.0.0.1:3306/forklift_dispatch?charset=utf8mb4
```

如果你本地 MySQL 的用户名、密码、端口或库名不同，直接修改 `backend/.env` 里的 `DATABASE_URL`。

首次切换 MySQL 时有两种方式：

```powershell
# 如本地 MySQL 还没有业务库和业务账号，可先用 root 创建。
# 本机已验证 root/root 可用；其他机器按实际 root 密码修改。
python scripts/prepare_mysql_user.py --root-user root --root-password root

# 方式一：把当前 SQLite 演示数据迁移到 MySQL，建议使用
python scripts/migrate_sqlite_to_mysql.py --reset

# 方式二：只写入全新的模拟数据
python run.py reset
```

也可以先在 MySQL 执行 `database/mysql_schema.sql` 建库建表，再运行 `python run.py seed` 写入模拟数据。

## 前端运行

```powershell
cd "E:\Project program\企业项目\无人调度车\调度系统\frontend"
npm.cmd install
npm.cmd run dev
```

访问 `http://127.0.0.1:5173`。演示账号：`admin`、`d001`，密码均为 `123456`。

## 当前核心流程

1. `admin` 登录，先在“取送货点”维护取货地址、送货地址，在“叉车管理”维护电叉车/油叉车台账，也可在“调度规则”用滑块调整派单优先级。
2. `admin` 在“调度任务”发布搬运任务，可用固定取送货点下拉框，也可切换到卫星地图直接标记本次任务取送货点；临时点在任务完成后自动停用。派单可切换“自动派单/手动派单”，自动派单按推荐分选择司机车辆，手动派单从候选列表指定车辆，系统写入企业微信消息记录。
3. `d001` 等司机登录，在“我的任务”接受或拒绝任务；拒绝必须填写原因。
4. 司机接受后，运行 `python scripts/gps_simulator.py --interval 2 --ticks 300` 可持续模拟叉车运动。完成任务时系统按 `forklift_positions` 轨迹自动计算公里数，并进入司机报表。
5. 需要全链路压测时，运行 `python scripts/gps_simulator.py --mode workday --ticks 160 --step-seconds 90 --max-created 60 --rollback`，系统会模拟管理员随机发布任务、自动派单、司机自动接收、叉车按速度行驶并完成任务；`--rollback` 用于体检不落库，去掉后会把模拟任务和 GPS 轨迹写入当前数据库。

## 后续接硬件定位

硬件组只需按 `forklift_positions` 表结构持续写入 `forklift_id、task_id、recorded_at、x、y、lat、lng、heading、speed、source、quality、area`。前端总览、叉车列表、调度推荐与任务距离计算读取同一批表；关闭 `.env` 中的 `SIMULATION_ENABLED` 后即可停止页面刷新时的内置模拟，也可单独运行 `backend/scripts/gps_simulator.py` 生成真实 GPS 流程的模拟轨迹。

如果硬件只写真实经纬度，建议先在“取送货点 -> 坐标标定”完成厂区四角 GPS 标定。系统会优先按数据库中的四角标定换算 `lat/lng -> x/y`；如果未完成标定，也可以在 `.env` 中配置 `MAP_GPS_NORTH、MAP_GPS_SOUTH、MAP_GPS_EAST、MAP_GPS_WEST` 四个厂区边界值作为兜底。GPS 模拟器生成的位置会被限制在四角标定围成的工作区内，并同步写入模拟 `lat/lng`。
