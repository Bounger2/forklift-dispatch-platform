<template>
  <section v-if="!token" class="login-shell">
    <form class="login-panel" @submit.prevent="login">
      <div class="brand-mark">FD</div>
      <h1>厂内叉车智能调度平台</h1>
      <p>任务池、调度引擎、实时定位、人车绑定、企微推送一体化管理</p>
      <label>
        账号
        <input v-model="loginForm.username" autocomplete="username" />
      </label>
      <label>
        密码
        <input v-model="loginForm.password" type="password" autocomplete="current-password" />
      </label>
      <button class="primary-btn" type="submit" :disabled="loading">
        <span class="btn-icon">></span>
        登录调度台
      </button>
      <div class="demo-users">
        演示账号：admin / d001，密码均为 123456
      </div>
      <p v-if="errorMessage" class="error-line">{{ errorMessage }}</p>
    </form>
  </section>

  <section v-else class="app-shell" :class="{ 'is-sidebar-hidden': sidebarHidden }">
    <button
      v-if="sidebarHidden"
      class="sidebar-show-btn"
      type="button"
      title="显示侧边栏"
      aria-label="显示侧边栏"
      @click="sidebarHidden = false"
    >
      菜单
    </button>
    <aside class="sidebar">
      <div class="sidebar__brand">
        <div class="brand-mark brand-mark--small">FD</div>
        <div class="sidebar__brand-copy">
          <strong>叉车调度</strong>
          <span>企业级运行台</span>
        </div>
        <button
          class="sidebar-toggle-btn"
          type="button"
          title="隐藏侧边栏"
          aria-label="隐藏侧边栏"
          @click="sidebarHidden = true"
        >
          &lt;&lt;
        </button>
      </div>
      <button
        v-for="item in nav"
        :key="item.key"
        class="nav-btn"
        :class="{ active: activeView === item.key }"
        :title="item.label"
        @click="activeView = item.key"
      >
        <span class="nav-btn__icon">{{ item.icon }}</span>
        <span class="nav-btn__label">{{ item.label }}</span>
      </button>
      <div class="sidebar__footer">
        <strong>{{ user?.name }}</strong>
        <span>{{ user?.role }} · {{ user?.department }}</span>
        <button class="ghost-btn" @click="logout">退出</button>
      </div>
    </aside>

    <main class="main">
      <header class="topbar">
        <div>
          <h2>{{ currentTitle }}</h2>
          <span>{{ nowText }} · 页面每 5 秒读取最新数据库位置</span>
        </div>
      </header>

      <p v-if="errorMessage" class="error-line">{{ errorMessage }}</p>

      <section v-if="activeView === 'overview'" class="view-stack">
        <div class="kpi-grid">
          <article v-for="card in kpiCards" :key="card.label" class="kpi-card">
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <small>{{ card.hint }}</small>
          </article>
        </div>

        <div class="overview-grid">
          <div class="map-panel">
            <div class="panel-title">
              <div>
                <h3>厂区实时总览</h3>
                <span>车载 GPS/北斗数据后续由硬件组写入数据库，本系统当前按同表结构模拟</span>
              </div>
              <button class="ghost-btn" @click="activeView = 'map'">维护点位</button>
            </div>
            <FactoryMap
              :vehicles="overview.vehicles"
              :points="overview.mapPoints"
              base-mode="satellite"
              :show-labels="false"
              :scale-meters="basemap.scaleMeters"
              :meters-per-unit="basemap.metersPerUnit"
              @select-vehicle="selectedVehicle = $event"
              @select-point="selectedPoint = $event"
            />
          </div>

          <div class="side-panels">
            <section class="panel">
              <div class="panel-title">
                <h3>待处理任务</h3>
                <button class="ghost-btn" @click="activeView = 'tasks'">任务池</button>
              </div>
              <div class="compact-list list-scroll list-scroll--small">
                <article v-for="task in pendingTasks" :key="task.id" class="compact-item">
                  <div>
                    <strong>{{ task.taskNo }}</strong>
                    <span>{{ task.originLabel }} -> {{ task.destLabel }}</span>
                  </div>
                  <b :class="`priority priority--${task.priority}`">{{ task.priority }}</b>
                </article>
              </div>
            </section>

            <section class="panel">
              <div class="panel-title">
                <h3>异常预警</h3>
                <button class="ghost-btn" @click="activeView = 'alerts'">闭环</button>
              </div>
              <div class="compact-list list-scroll list-scroll--small">
                <article v-for="alert in overview.alerts" :key="alert.id" class="compact-item compact-item--alert">
                  <div>
                    <strong>{{ alert.title }}</strong>
                    <span>{{ alert.suggestion }}</span>
                  </div>
                  <b :class="`severity severity--${alert.severity}`">{{ alert.severity }}</b>
                </article>
              </div>
            </section>
          </div>
        </div>

        <section class="panel driver-gantt-panel">
          <div class="panel-title">
            <div>
              <h3>司机当天任务甘特图</h3>
              <span>{{ overview.driverGantt?.date || '' }} · 横轴为当天 00:00-24:00，展示司机任务工作时间分布</span>
            </div>
          </div>
          <div class="driver-gantt">
            <div class="driver-gantt__header">
              <div class="driver-gantt__driver-cell">司机</div>
              <div class="driver-gantt__timeline">
                <span v-for="hour in ganttHours" :key="hour" :style="{ left: `${(hour / 24) * 100}%` }">{{ String(hour).padStart(2, '0') }}:00</span>
              </div>
            </div>
            <div class="driver-gantt__body">
              <div v-for="row in overview.driverGantt?.rows || []" :key="row.driverId" class="driver-gantt__row">
                <div class="driver-gantt__driver-cell">
                  <strong>{{ row.name }}</strong>
                  <small>{{ row.employeeNo }} · {{ row.team || '-' }}</small>
                </div>
                <div class="driver-gantt__track">
                  <span v-for="hour in ganttHours" :key="hour" class="driver-gantt__gridline" :style="{ left: `${(hour / 24) * 100}%` }"></span>
                  <div
                    v-for="segment in row.segments"
                    :key="segment.taskId"
                    class="driver-gantt__bar"
                    :class="`driver-gantt__bar--${segment.status}`"
                    :style="ganttSegmentStyle(segment)"
                    :title="`${segment.taskNo} ${segment.startLabel}-${segment.endLabel} ${segment.origin} -> ${segment.destination}`"
                  >
                    <strong>{{ segment.taskNo.replace('TASK-', '') }}</strong>
                    <span>{{ segment.startLabel }}-{{ segment.endLabel }}</span>
                  </div>
                </div>
              </div>
              <div v-if="!(overview.driverGantt?.rows || []).length" class="empty-state">当前没有司机排班数据</div>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-title">
            <h3>车辆运行状态</h3>
            <span>{{ overview.vehicles.length }} 台叉车</span>
          </div>
          <div class="table-wrap table-wrap--medium">
            <table>
              <thead>
                <tr>
                  <th>车辆</th>
                  <th>司机</th>
                  <th>状态</th>
                  <th>能源</th>
                  <th>区域</th>
                  <th>速度</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="vehicle in overview.vehicles" :key="vehicle.id">
                  <td><strong>{{ vehicle.code }}</strong><small>{{ vehicle.model }}</small></td>
                  <td>{{ vehicle.driver?.name || '未绑定' }}</td>
                  <td><span :class="`status status--${vehicle.status}`">{{ vehicle.status }}</span></td>
                  <td>
                    <div class="battery"><span :style="{ width: `${vehicle.energyLevel}%` }"></span></div>
                    {{ vehicle.powerType === 'electric' ? '电' : '油' }} {{ vehicle.energyLevel }}%
                  </td>
                  <td>{{ vehicle.currentArea }}</td>
                  <td>{{ vehicle.speed }} km/h</td>
                  <td>
                    <button class="mini-btn" @click="toggleVehicleLock(vehicle)">
                      {{ vehicle.status === 'disabled' ? '启用' : '停用' }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </section>

      <section v-if="activeView === 'tasks'" class="work-grid task-work-grid">
        <form class="panel form-panel" @submit.prevent="createTask">
          <div class="panel-title">
            <h3>发布搬运任务</h3>
            <span>管理员统一发布任务，系统按自动/手动模式派给司机。</span>
          </div>
          <div class="rule-toolbar task-location-mode">
            <button class="mini-btn" :class="{ active: taskLocationMode === 'select' }" type="button" @click="taskLocationMode = 'select'">下拉选择</button>
            <button class="mini-btn" :class="{ active: taskLocationMode === 'map' }" type="button" @click="taskLocationMode = 'map'">地图标点</button>
          </div>
          <div v-if="taskLocationMode === 'select'" class="form-grid">
            <label>取货地址<select v-model="taskForm.originPointId"><option v-for="p in transportPoints" :value="p.id" :key="p.id">{{ p.name }}</option></select></label>
            <label>送货地址<select v-model="taskForm.destPointId"><option v-for="p in transportPoints" :value="p.id" :key="p.id">{{ p.name }}</option></select></label>
          </div>
          <div v-else class="task-map-picker">
            <div class="task-map-picker__toolbar">
              <div class="rule-toolbar">
                <button class="mini-btn" :class="{ active: activeTaskMapTarget === 'origin' }" type="button" @click="activeTaskMapTarget = 'origin'">标记取货点</button>
                <button class="mini-btn" :class="{ active: activeTaskMapTarget === 'dest' }" type="button" @click="activeTaskMapTarget = 'dest'">标记送货点</button>
              </div>
              <div class="task-map-picker__summary">
                <span :class="{ ready: taskMapDraft.origin }">取货：{{ taskMapLabel('origin') }}</span>
                <span :class="{ ready: taskMapDraft.dest }">送货：{{ taskMapLabel('dest') }}</span>
              </div>
            </div>
            <FactoryMap
              class="task-picker-map"
              editable
              :vehicles="overview.vehicles"
              :points="taskMapFormPoints"
              base-mode="satellite"
              :show-labels="false"
              :scale-meters="basemap.scaleMeters"
              :meters-per-unit="basemap.metersPerUnit"
              @map-click="setTaskMapPoint"
              @select-point="selectTaskMapExistingPoint"
            />
          </div>
          <div class="form-grid">
            <label>货物类型<input v-model="taskForm.cargoType" /></label>
            <label>重量 kg<input v-model.number="taskForm.estimatedWeight" type="number" /></label>
            <label>托盘/件数<input v-model.number="taskForm.palletCount" type="number" min="1" /></label>
            <label>优先级<select v-model="taskForm.priority"><option>S</option><option>A</option><option>B</option><option>C</option></select></label>
          </div>
          <label>备注<textarea v-model="taskForm.note" rows="3"></textarea></label>
          <button class="primary-btn" type="submit">提交任务</button>
        </form>

        <section class="panel">
          <div class="panel-title">
            <h3>任务池</h3>
            <div class="dispatch-mode">
              <span>派单模式</span>
              <button class="mini-btn" :class="{ active: dispatchMode === 'auto' }" @click="dispatchMode = 'auto'">自动派单</button>
              <button class="mini-btn" :class="{ active: dispatchMode === 'manual' }" @click="dispatchMode = 'manual'">手动派单</button>
            </div>
          </div>
          <div class="list-filter-bar">
            <label>状态<select v-model="taskFilters.status"><option value="all">全部状态</option><option v-for="status in taskStatusOptions.filter((item) => item !== 'all')" :key="status" :value="status">{{ status }}</option></select></label>
            <label>优先级<select v-model="taskFilters.priority"><option value="all">全部优先级</option><option v-for="priority in taskPriorityOptions.filter((item) => item !== 'all')" :key="priority" :value="priority">{{ priority }}</option></select></label>
            <label>关键词<input v-model.trim="taskFilters.keyword" placeholder="工单、路线、货物、司机" /></label>
            <span>显示 {{ filteredTasks.length }} / {{ tasks.length }} 条</span>
          </div>
          <div class="table-wrap table-wrap--tall">
            <table>
              <thead>
                <tr>
                  <th>工单</th>
                  <th>路线</th>
                  <th>货物</th>
                  <th>优先级</th>
                  <th>状态</th>
                  <th>车辆/司机</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="task in filteredTasks" :key="task.id">
                  <td><strong>{{ task.taskNo }}</strong><small>{{ formatTime(task.createdAt) }}</small></td>
                  <td>{{ task.originLabel }} -> {{ task.destLabel }}</td>
                  <td>{{ task.cargoType }} / {{ task.estimatedWeight }}kg</td>
                  <td><b :class="`priority priority--${task.priority}`">{{ task.priority }}</b></td>
                  <td><span :class="`status status--${task.status}`">{{ task.status }}</span></td>
                  <td>
                    {{ task.assignedForklift?.code || '-' }} / {{ task.assignedDriver?.name || '-' }}
                    <small v-if="task.assignedDriver">司机账号：{{ task.assignedDriver.employeeNo?.toLowerCase() }}</small>
                  </td>
                  <td class="row-actions">
                    <button class="mini-btn" :disabled="!canDispatch(task)" @click="previewTask(task)">推荐</button>
                    <button v-if="dispatchMode === 'auto'" class="mini-btn" :disabled="!canDispatch(task)" @click="dispatchTask(task)">自动派单</button>
                    <button v-else class="mini-btn" :disabled="!canDispatch(task)" @click="openManualDispatch(task)">手动派单</button>
                    <button class="mini-btn" @click="markComplete(task)">完成</button>
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-if="!filteredTasks.length" class="empty-state">当前筛选条件下没有任务</div>
          </div>
        </section>

        <section v-if="recommendation" class="panel recommendation-panel">
          <div class="panel-title">
            <h3>调度推荐</h3>
            <button class="ghost-btn" @click="recommendation = null">关闭</button>
          </div>
          <p v-if="recommendation.task" class="form-note">
            当前工单：{{ recommendation.task.taskNo }}。自动派单会选择第一名；手动派单可指定下方候选车辆。
          </p>
          <div class="compact-list list-scroll list-scroll--medium">
            <article v-for="row in recommendation.candidates" :key="row.vehicle.id" class="candidate-row">
              <div>
                <strong>{{ row.vehicle.code }} / {{ row.driver.name }}</strong>
                <span>司机账号 {{ row.driver.employeeNo?.toLowerCase() }}，ETA {{ row.etaMinutes }} 分钟，距离 {{ row.distance }}，评分 {{ row.score }}</span>
              </div>
              <div class="score-bar"><span :style="{ width: `${row.score}%` }"></span></div>
              <button v-if="dispatchMode === 'manual'" class="mini-btn" @click="dispatchTask(recommendation.task, row.vehicle.id)">选此派单</button>
            </article>
            <article v-if="!recommendation.candidates.length" class="empty-state">当前没有可推荐车辆</article>
          </div>
          <details>
            <summary>被过滤车辆</summary>
            <div v-for="row in recommendation.rejected" :key="row.vehicle.id" class="rejected-row">
              {{ row.vehicle.code }}：{{ row.reason }}
            </div>
          </details>
        </section>
      </section>

      <section v-if="activeView === 'map'" class="work-grid">
        <div class="map-panel map-panel--edit">
          <div class="panel-title">
            <div>
              <h3>取送货点管理</h3>
              <span>{{ mapEditMode === 'calibration' ? '选择四个厂区边界角点，点击地图自动填入 XY 与经纬度，确认后保存。' : '点击地图自动获取 XY 与经纬度，维护管理员发布任务时可选择的取货地址和送货地址。' }}</span>
            </div>
            <div class="rule-toolbar">
              <button class="mini-btn" :class="{ active: mapEditMode === 'point' }" type="button" @click="mapEditMode = 'point'">点位模式</button>
              <button class="mini-btn" :class="{ active: mapEditMode === 'calibration' }" type="button" @click="mapEditMode = 'calibration'">坐标标定</button>
            </div>
          </div>
          <FactoryMap
            editable
            :vehicles="overview.vehicles"
            :points="mapPoints"
            :calibration-points="mapEditMode === 'calibration' ? calibrationPoints : []"
            :calibration-mode="mapEditMode === 'calibration'"
            :active-calibration-key="activeCalibrationKey"
            base-mode="satellite"
            :show-labels="false"
            :scale-meters="basemap.scaleMeters"
            :meters-per-unit="basemap.metersPerUnit"
            :draft-point="draftPoint"
            @map-click="handleMapClick"
            @select-point="fillPoint"
            @select-calibration="selectCalibrationPoint"
          />
        </div>
        <section v-if="mapEditMode === 'calibration'" class="panel calibration-panel">
          <div class="panel-title">
            <div>
              <h3>GPS 坐标标定</h3>
              <span>{{ calibrationReady ? '四角标定已完成，硬件 GPS 将按此关系换算为地图 XY。' : '请依次选择西北、东北、东南、西南四个角点，在地图上点击后保存。' }}</span>
            </div>
            <button class="primary-btn" type="button" @click="saveCalibration">保存标定</button>
          </div>
          <div class="calibration-grid">
            <article
              v-for="corner in calibrationPoints"
              :key="corner.cornerKey"
              class="calibration-card"
              :class="{ active: activeCalibrationKey === corner.cornerKey }"
            >
              <div class="calibration-card__head">
                <strong>{{ corner.label }}</strong>
                <button class="mini-btn" type="button" @click="activeCalibrationKey = corner.cornerKey">标记此角</button>
              </div>
              <div class="form-grid">
                <label>X<input v-model.number="corner.x" type="number" step="0.01" /></label>
                <label>Y<input v-model.number="corner.y" type="number" step="0.01" /></label>
                <label>纬度<input v-model.number="corner.lat" type="number" step="0.0000001" placeholder="31.xxxxxx" /></label>
                <label>经度<input v-model.number="corner.lng" type="number" step="0.0000001" placeholder="120.xxxxxx" /></label>
              </div>
            </article>
          </div>
        </section>
        <form class="panel form-panel" @submit.prevent="savePoint">
          <div class="panel-title">
            <h3>{{ pointEditId ? '修改取送货点' : '新增取送货点' }}</h3>
            <button v-if="pointEditId" class="ghost-btn" type="button" @click="resetPointForm">取消编辑</button>
          </div>
          <div class="form-grid">
            <label>名称<input v-model="pointForm.name" /></label>
            <label>类型<select v-model="pointForm.pointType"><option value="pickup">取货点</option><option value="dropoff">放货点</option><option value="dock">装卸口</option><option value="charging">充电区</option><option value="maintenance">维修点</option><option value="parking">待命区</option><option value="lora">LoRa点</option><option value="handover">交接点</option></select></label>
            <label>区域<input v-model="pointForm.area" /></label>
            <label>X<input v-model.number="pointForm.x" type="number" step="0.01" /></label>
            <label>Y<input v-model.number="pointForm.y" type="number" step="0.01" /></label>
            <label>围栏半径<input v-model.number="pointForm.geofenceRadius" type="number" /></label>
            <label>纬度<input v-model.number="pointForm.lat" type="number" step="0.0000001" placeholder="GPS 纬度" /></label>
            <label>经度<input v-model.number="pointForm.lng" type="number" step="0.0000001" placeholder="GPS 经度" /></label>
          </div>
          <label>联系人<input v-model="pointForm.contact" /></label>
          <button class="ghost-btn" type="button" @click="convertPointGpsToXY">根据经纬度换算 X/Y</button>
          <button class="primary-btn" type="submit">{{ pointEditId ? '保存修改' : '保存点位' }}</button>
        </form>
        <section class="panel address-table-panel">
          <div class="panel-title">
            <h3>地址清单</h3>
            <span>{{ filteredMapPoints.length }} / {{ mapPoints.length }} 个点位</span>
          </div>
          <div class="list-filter-bar">
            <label>类型<select v-model="pointFilters.type"><option value="all">全部类型</option><option v-for="type in pointTypeOptions.filter((item) => item !== 'all')" :key="type" :value="type">{{ pointTypeLabel(type) }}</option></select></label>
            <label>状态<select v-model="pointFilters.status"><option value="enabled">启用</option><option value="all">全部</option><option value="disabled">停用</option></select></label>
            <label>关键词<input v-model.trim="pointFilters.keyword" placeholder="名称、区域、联系人、GPS" /></label>
          </div>
          <div class="table-wrap table-wrap--medium">
            <table>
              <thead><tr><th>名称</th><th>类型</th><th>区域</th><th>坐标</th><th>GPS</th><th>围栏</th><th>状态</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="point in filteredMapPoints" :key="point.id">
                  <td><strong>{{ point.name }}</strong><small>{{ point.contact || '-' }}</small></td>
                  <td>{{ pointTypeLabel(point.pointType) }}</td>
                  <td>{{ point.area }}</td>
                  <td>{{ point.x }}, {{ point.y }}</td>
                  <td>{{ point.lat && point.lng ? `${point.lat}, ${point.lng}` : '-' }}</td>
                  <td>{{ point.geofenceRadius }}m</td>
                  <td><span :class="`status status--${point.enabled ? 'completed' : 'disabled'}`">{{ point.enabled ? '启用' : '停用' }}</span></td>
                  <td class="row-actions">
                    <button class="mini-btn" @click="fillPoint(point)">修改</button>
                    <button class="mini-btn" :disabled="!point.enabled" @click="deletePoint(point)">{{ point.enabled ? '停用' : '已停用' }}</button>
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-if="!filteredMapPoints.length" class="empty-state">当前筛选条件下没有点位</div>
          </div>
        </section>
      </section>

      <section v-if="activeView === 'vehicles'" class="work-grid vehicle-work-grid">
        <form class="panel form-panel" @submit.prevent="saveVehicle">
          <div class="panel-title">
            <div>
              <h3>{{ editingVehicleId ? '修改叉车' : '新增叉车' }}</h3>
              <span>支持电叉车、油叉车等不同动力类型，参与调度与地图定位。</span>
            </div>
            <button v-if="editingVehicleId" class="ghost-btn" type="button" @click="resetVehicleForm">取消编辑</button>
          </div>
          <div class="form-grid">
            <label>车辆编号<input v-model="vehicleForm.code" /></label>
            <label>车牌/内部牌号<input v-model="vehicleForm.plateNo" /></label>
            <label>车型<input v-model="vehicleForm.model" /></label>
            <label>动力类型<select v-model="vehicleForm.powerType"><option value="electric">电动叉车</option><option value="diesel">柴油叉车</option><option value="gasoline">汽油叉车</option><option value="lpg">液化气叉车</option></select></label>
            <label>吨位<input v-model.number="vehicleForm.tonnage" type="number" step="0.1" /></label>
            <label>状态<select v-model="vehicleForm.status"><option value="idle">idle</option><option value="assigned">assigned</option><option value="executing">executing</option><option value="maintenance">maintenance</option><option value="fault">fault</option><option value="disabled">disabled</option></select></label>
            <label>电量 %<input v-model.number="vehicleForm.batteryLevel" type="number" min="0" max="100" /></label>
            <label>油量 %<input v-model.number="vehicleForm.fuelLevel" type="number" min="0" max="100" /></label>
            <label>区域<input v-model="vehicleForm.currentArea" /></label>
            <label>在线<select v-model="vehicleForm.online"><option :value="true">在线</option><option :value="false">离线</option></select></label>
            <label>X<input v-model.number="vehicleForm.x" type="number" step="0.01" /></label>
            <label>Y<input v-model.number="vehicleForm.y" type="number" step="0.01" /></label>
          </div>
          <label>备注<textarea v-model="vehicleForm.note" rows="3"></textarea></label>
          <button class="primary-btn" type="submit">{{ editingVehicleId ? '保存修改' : '新增叉车' }}</button>
        </form>

        <section class="panel">
          <div class="panel-title">
            <h3>叉车台账</h3>
            <span>{{ filteredVehicles.length }} / {{ vehicles.length }} 台车辆</span>
          </div>
          <div class="list-filter-bar">
            <label>状态<select v-model="vehicleFilters.status"><option value="all">全部状态</option><option v-for="status in vehicleStatusOptions.filter((item) => item !== 'all')" :key="status" :value="status">{{ status }}</option></select></label>
            <label>动力<select v-model="vehicleFilters.powerType"><option value="all">全部动力</option><option v-for="type in vehiclePowerOptions.filter((item) => item !== 'all')" :key="type" :value="type">{{ powerTypeLabel(type) }}</option></select></label>
            <label>关键词<input v-model.trim="vehicleFilters.keyword" placeholder="编号、牌号、车型、区域、司机" /></label>
          </div>
          <div class="table-wrap table-wrap--medium">
            <table>
              <thead><tr><th>编号</th><th>动力</th><th>吨位</th><th>状态</th><th>能源</th><th>位置</th><th>绑定司机</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="vehicle in filteredVehicles" :key="vehicle.id">
                  <td><strong>{{ vehicle.code }}</strong><small>{{ vehicle.plateNo }} · {{ vehicle.model }}</small></td>
                  <td>{{ powerTypeLabel(vehicle.powerType) }}</td>
                  <td>{{ vehicle.tonnage }}T</td>
                  <td><span :class="`status status--${vehicle.status}`">{{ vehicle.status }}</span></td>
                  <td>{{ vehicle.powerType === 'electric' ? vehicle.batteryLevel : vehicle.fuelLevel }}%</td>
                  <td>{{ vehicle.currentArea }}<small>{{ vehicle.x }}, {{ vehicle.y }}</small></td>
                  <td>{{ vehicle.driver?.name || '-' }}</td>
                  <td class="row-actions">
                    <button class="mini-btn" @click="editVehicle(vehicle)">修改</button>
                    <button class="mini-btn" :disabled="vehicle.status === 'disabled'" @click="deleteVehicle(vehicle)">停用</button>
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-if="!filteredVehicles.length" class="empty-state">当前筛选条件下没有车辆</div>
          </div>
        </section>
      </section>

      <section v-if="activeView === 'rules'" class="work-grid">
        <section class="panel">
          <div class="panel-title">
            <h3>调度规则库</h3>
            <span>评分权重可直接拖动，数值越高越优先影响自动派单。</span>
          </div>
          <div class="rule-priority-list list-scroll list-scroll--medium">
            <article v-for="rule in scoreRules" :key="rule.id" class="rule-priority-card">
              <div>
                <strong>{{ rule.name }}</strong>
                <span>{{ rule.description }}</span>
              </div>
              <div class="rule-weight">
                <b>{{ Math.round((rule.weight || 0) * 100) }}%</b>
                <input
                  class="rule-slider"
                  type="range"
                  min="0"
                  max="0.6"
                  step="0.01"
                  v-model.number="rule.weight"
                  @change="saveRuleWeight(rule)"
                />
              </div>
            </article>
          </div>
        </section>

        <form class="panel form-panel" @submit.prevent="createRule">
          <div class="panel-title"><h3>用户自定义规则</h3></div>
          <label>规则名称<input v-model="ruleForm.name" /></label>
          <div class="form-grid">
            <label>分类<select v-model="ruleForm.category"><option>manual</option><option>score</option><option>exception</option><option>priority</option></select></label>
            <label>类型<input v-model="ruleForm.ruleType" /></label>
            <label>优先级<input v-model.number="ruleForm.priority" type="number" /></label>
            <label>权重/加权<input v-model.number="ruleForm.weight" type="number" step="0.01" /></label>
          </div>
          <label>条件 JSON<textarea v-model="ruleForm.conditionJsonText" rows="5"></textarea></label>
          <label>动作 JSON<textarea v-model="ruleForm.actionJsonText" rows="5"></textarea></label>
          <label>说明<textarea v-model="ruleForm.description" rows="3"></textarea></label>
          <button class="primary-btn" type="submit">新增规则</button>
        </form>

        <section class="panel rules-table-panel">
          <div class="panel-title">
            <h3>全部规则</h3>
            <span>过滤、插单、调单、异常、报表推送规则集中维护。</span>
          </div>
          <div class="rule-toolbar">
            <button v-for="cat in ruleCategories" :key="cat" class="mini-btn" :class="{ active: ruleFilter === cat }" @click="ruleFilter = cat">
              {{ cat }}
            </button>
            <input class="toolbar-search" v-model.trim="ruleSearch" placeholder="搜索规则名称、编号、说明" />
            <span class="filter-count">显示 {{ filteredRules.length }} / {{ rules.length }} 条</span>
          </div>
          <div class="table-wrap table-wrap--medium">
            <table>
              <thead>
                <tr>
                  <th>规则</th>
                  <th>分类</th>
                  <th>类型</th>
                  <th>权重/优先级</th>
                  <th>状态</th>
                  <th>说明</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="rule in filteredRules" :key="rule.id">
                  <td><strong>{{ rule.name }}</strong><small>{{ rule.code }}</small></td>
                  <td>{{ rule.category }}</td>
                  <td>{{ rule.ruleType }}</td>
                  <td>{{ rule.weight }} / {{ rule.priority }}</td>
                  <td>
                    <span :class="`status status--${rule.enabled ? 'completed' : 'disabled'}`">
                      {{ rule.enabled ? '启用' : '停用' }}
                    </span>
                  </td>
                  <td>{{ rule.description }}</td>
                  <td class="row-actions">
                    <button class="mini-btn" @click="toggleRule(rule)">{{ rule.enabled ? '停用' : '启用' }}</button>
                    <button class="mini-btn" :disabled="!rule.editable" @click="deleteRule(rule)">删除</button>
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-if="!filteredRules.length" class="empty-state">当前筛选条件下没有规则</div>
          </div>
        </section>
      </section>

      <section v-if="activeView === 'schedules'" class="view-stack">
        <section class="panel">
          <div class="panel-title"><h3>排班模板</h3></div>
          <div class="shift-grid">
            <article v-for="shift in schedules.shiftTemplates" :key="shift.id" class="shift-card">
              <strong>{{ shift.name }}</strong>
              <span>{{ shift.startTime }} - {{ shift.endTime }}</span>
              <small>{{ shift.area }} · 休息 {{ shift.restMinutes }} 分钟</small>
            </article>
          </div>
        </section>
        <section class="work-grid">
          <form class="panel form-panel" @submit.prevent="saveAssignment">
            <div class="panel-title">
              <div>
                <h3>{{ editingAssignmentId ? '修改排班' : '新增排班' }}</h3>
                <span>维护司机、车辆、班次和负责区域。</span>
              </div>
              <button v-if="editingAssignmentId" class="ghost-btn" type="button" @click="resetScheduleForm">取消编辑</button>
            </div>
            <div class="form-grid">
              <label>日期<input v-model="scheduleForm.shiftDate" type="date" /></label>
              <label>班次<select v-model="scheduleForm.shiftCode"><option v-for="shift in schedules.shiftTemplates" :key="shift.code" :value="shift.code">{{ shift.code }} · {{ shift.name }}</option></select></label>
              <label>司机<select v-model="scheduleForm.driverId"><option value="">请选择司机</option><option v-for="driver in drivers" :key="driver.id" :value="driver.id">{{ driver.employeeNo }} · {{ driver.name }}</option></select></label>
              <label>车辆<select v-model="scheduleForm.forkliftId"><option value="">不指定车辆</option><option v-for="vehicle in vehicles" :key="vehicle.id" :value="vehicle.id">{{ vehicle.code }} · {{ vehicle.status }}</option></select></label>
              <label>区域<input v-model="scheduleForm.area" /></label>
              <label>状态<select v-model="scheduleForm.status"><option value="scheduled">scheduled</option><option value="signed_in">signed_in</option><option value="off">off</option><option value="leave">leave</option></select></label>
            </div>
            <button class="primary-btn" type="submit">{{ editingAssignmentId ? '保存排班' : '新增排班' }}</button>
          </form>

          <form class="panel form-panel" @submit.prevent="bindVehicle">
            <div class="panel-title">
              <div>
                <h3>司机车辆绑定修改</h3>
                <span>用于班前刷卡异常、临时换车、换班补位等人工改绑场景</span>
              </div>
            </div>
            <div class="form-grid">
              <label>
                司机
                <select v-model="bindingForm.driverId">
                  <option value="">请选择司机</option>
                  <option v-for="driver in drivers" :key="driver.id" :value="driver.id">
                    {{ driver.employeeNo }} · {{ driver.name }} · {{ driver.team }}
                  </option>
                </select>
              </label>
              <label>
                车辆
                <select v-model="bindingForm.forkliftId">
                  <option value="">请选择车辆</option>
                  <option v-for="vehicle in vehicles" :key="vehicle.id" :value="vehicle.id">
                    {{ vehicle.code }} · {{ vehicle.status }} · {{ vehicle.energyLevel }}%
                  </option>
                </select>
              </label>
              <label>
                班次
                <select v-model="bindingForm.shiftCode">
                  <option v-for="shift in schedules.shiftTemplates" :key="shift.code" :value="shift.code">
                    {{ shift.code }} · {{ shift.name }}
                  </option>
                </select>
              </label>
              <label>
                绑定方式
                <select v-model="bindingForm.bindMethod">
                  <option value="manual">管理员人工绑定</option>
                  <option value="rfid">RFID刷卡绑定</option>
                  <option value="wecom">企业微信确认</option>
                </select>
              </label>
            </div>
            <p class="form-note">保存后会自动关闭该司机或该车辆原有的 active 绑定，避免一人多车或一车多人。</p>
            <button class="primary-btn" type="submit">保存绑定 / 换绑</button>
          </form>

          <section class="panel">
            <div class="panel-title">
              <h3>当前有效绑定</h3>
              <span>{{ filteredActiveBindings.length }} / {{ activeBindings.length }} 条 active 记录</span>
            </div>
            <div class="list-filter-bar list-filter-bar--single">
              <label>关键词<input v-model.trim="bindingFilters.keyword" placeholder="司机、工号、车辆、班次" /></label>
            </div>
            <div class="compact-list list-scroll list-scroll--medium">
              <article v-for="binding in filteredActiveBindings" :key="binding.id" class="compact-item">
                <div>
                  <strong>{{ binding.forklift?.code }} / {{ binding.driver?.name }}</strong>
                  <span>{{ binding.shiftCode }} · {{ binding.bindMethod }} · {{ formatTime(binding.boundAt) }}</span>
                </div>
                <button class="mini-btn" @click="closeBinding(binding)">解除</button>
              </article>
              <article v-if="!filteredActiveBindings.length" class="empty-state">当前筛选条件下没有有效绑定</article>
            </div>
          </section>
        </section>

        <section class="panel">
          <div class="panel-title">
            <h3>当班排班与绑定</h3>
            <span>可从排班行快速带入司机和车辆后改绑</span>
          </div>
          <div class="list-filter-bar">
            <label>状态<select v-model="scheduleFilters.status"><option value="all">全部状态</option><option v-for="status in scheduleStatusOptions.filter((item) => item !== 'all')" :key="status" :value="status">{{ status }}</option></select></label>
            <label>关键词<input v-model.trim="scheduleFilters.keyword" placeholder="班次、司机、车辆、区域" /></label>
            <span>显示 {{ filteredAssignments.length }} / {{ schedules.assignments.length }} 条</span>
          </div>
          <div class="table-wrap table-wrap--medium">
            <table>
              <thead><tr><th>班次</th><th>司机</th><th>车辆</th><th>区域</th><th>签到状态</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="row in filteredAssignments" :key="row.id">
                  <td>{{ row.shiftCode }}</td>
                  <td>{{ row.driver?.name }}</td>
                  <td>{{ row.forklift?.code }}</td>
                  <td>{{ row.area }}</td>
                  <td><span class="status status--idle">{{ row.status }}</span></td>
                  <td class="row-actions">
                    <button class="mini-btn" @click="prefillBinding(row)">带入绑定</button>
                    <button class="mini-btn" @click="editAssignment(row)">修改</button>
                    <button class="mini-btn" @click="deleteAssignment(row)">删除</button>
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-if="!filteredAssignments.length" class="empty-state">当前筛选条件下没有排班记录</div>
          </div>
        </section>
      </section>

      <section v-if="activeView === 'driverHome'" class="view-stack driver-home">
        <section class="panel">
          <div class="panel-title">
            <div>
              <h3>司机主页</h3>
              <span>上线后等待管理员绑定叉车，也可以从空闲叉车列表发起申请。</span>
            </div>
            <div class="driver-status-actions">
              <span :class="`status status--${driverIsOnline ? 'completed' : 'disabled'}`">
                {{ driverIsOnline ? '已上线' : '已下线' }}
              </span>
              <button class="primary-btn" type="button" @click="toggleDriverOnline">
                {{ driverIsOnline ? '下线' : '上线' }}
              </button>
            </div>
          </div>
          <div class="driver-home-summary">
            <article>
              <span>绑定叉车</span>
              <strong>{{ currentDriverForklift?.code || '未绑定' }}</strong>
              <small>{{ currentDriverForklift ? `${currentDriverForklift.currentArea} · ${currentDriverForklift.energyLevel}%` : '上线后由管理员绑定' }}</small>
            </article>
            <article>
              <span>当前任务</span>
              <strong>{{ driverActiveTasks.length }}</strong>
              <small>待接收/执行中任务</small>
            </article>
            <article>
              <span>{{ periodLabel(driverHomeReport.period) }}完成</span>
              <strong>{{ driverHomeRow.taskCount }}</strong>
              <small>{{ driverHomeReport.start ? `${driverHomeReport.start.slice(0, 10)} 至 ${driverHomeReport.end.slice(0, 10)}` : '暂无周期数据' }}</small>
            </article>
            <article>
              <span>总公里数</span>
              <strong>{{ driverHomeRow.totalDistance }} km</strong>
              <small>作业时长 {{ driverHomeRow.totalMinutes }} 分钟</small>
            </article>
          </div>
        </section>

        <section class="driver-chart-grid">
          <section class="panel">
            <div class="panel-title">
              <div>
                <h3>任务公里数</h3>
                <span>按当前周期展示已完成任务的运输公里数。</span>
              </div>
              <select class="period-select" v-model="driverHomeReportPeriod" @change="loadDriverHomeReport">
                <option value="day">本日</option>
                <option value="week">本周</option>
                <option value="month">本月</option>
                <option value="quarter">本季度</option>
                <option value="year">本年</option>
              </select>
            </div>
            <div ref="driverHomeTaskChartEl" class="echart-box"></div>
          </section>
          <section class="panel">
            <div class="panel-title">
              <div>
                <h3>作业时长</h3>
                <span>按接收时间到完成时间统计每单耗时。</span>
              </div>
            </div>
            <div ref="driverHomeDistanceChartEl" class="echart-box"></div>
          </section>
        </section>

        <section class="panel">
          <div class="panel-title">
            <div>
              <h3>空闲叉车申请</h3>
              <span>地图显示可申请空闲叉车位置；申请后由管理员确认并完成绑定。</span>
            </div>
            <button class="ghost-btn" type="button" @click="loadOverview">刷新位置</button>
          </div>
          <FactoryMap
            class="driver-home-map"
            :vehicles="driverMapVehicles"
            :points="overview.mapPoints"
            base-mode="satellite"
            :show-labels="false"
            :scale-meters="basemap.scaleMeters"
            :meters-per-unit="basemap.metersPerUnit"
          />
          <div class="list-filter-bar">
            <label>动力<select v-model="driverForkliftFilters.powerType"><option value="all">全部动力</option><option v-for="type in vehiclePowerOptions.filter((item) => item !== 'all')" :key="type" :value="type">{{ powerTypeLabel(type) }}</option></select></label>
            <label>关键词<input v-model.trim="driverForkliftFilters.keyword" placeholder="编号、车型、区域" /></label>
            <span>可申请 {{ filteredAvailableForklifts.length }} / {{ availableForklifts.length }} 台</span>
          </div>
          <div class="driver-forklift-list list-scroll list-scroll--medium">
            <article v-if="currentDriverForklift" class="driver-forklift-card bound">
              <div>
                <strong>{{ currentDriverForklift.code }}</strong>
                <span>当前绑定 · {{ currentDriverForklift.currentArea }}</span>
              </div>
              <b>{{ currentDriverForklift.energyLevel }}%</b>
            </article>
            <article v-for="vehicle in filteredAvailableForklifts" :key="vehicle.id" class="driver-forklift-card">
              <div>
                <strong>{{ vehicle.code }}</strong>
                <span>{{ vehicle.model }} · {{ vehicle.currentArea }} · {{ vehicle.powerType }}</span>
              </div>
              <b>{{ vehicle.energyLevel }}%</b>
              <button class="mini-btn" type="button" :disabled="!driverIsOnline || !!currentDriverForklift" @click="requestForklift(vehicle)">
                申请
              </button>
            </article>
            <article v-if="!filteredAvailableForklifts.length && !currentDriverForklift" class="empty-state">当前筛选条件下没有可申请的空闲叉车。</article>
          </div>
        </section>
      </section>

      <section v-if="activeView === 'driverTasks'" class="view-stack">
        <section class="panel">
          <div class="panel-title">
            <div>
              <h3>我的运输任务</h3>
              <span>司机在企业微信收到任务提醒后，登录系统接受或拒绝；完成后系统按 GPS 轨迹自动计算公里数。</span>
            </div>
            <button class="ghost-btn" @click="loadDriverTasks">刷新任务</button>
          </div>
          <div class="list-filter-bar">
            <label>状态<select v-model="driverTaskFilters.status"><option value="all">全部状态</option><option v-for="status in driverTaskStatusOptions.filter((item) => item !== 'all')" :key="status" :value="status">{{ status }}</option></select></label>
            <label>关键词<input v-model.trim="driverTaskFilters.keyword" placeholder="工单、路线、货物、车辆" /></label>
            <span>显示 {{ filteredDriverTasks.length }} / {{ driverTasks.length }} 条</span>
          </div>
          <div class="driver-task-grid list-scroll list-scroll--tall">
            <article v-for="task in filteredDriverTasks" :key="task.id" class="driver-task-card">
              <div class="driver-task-card__head">
                <div>
                  <strong>{{ task.taskNo }}</strong>
                  <span>{{ task.originLabel }} -> {{ task.destLabel }}</span>
                </div>
                <b :class="`status status--${task.status}`">{{ task.status }}</b>
              </div>
              <div class="task-meta">
                <span>货物：{{ task.cargoType }}</span>
                <span>重量：{{ task.estimatedWeight }}kg</span>
                <span>车辆：{{ task.assignedForklift?.code || '-' }}</span>
                <span>接收：{{ formatTime(task.acceptedAt) }}</span>
                <span>完成：{{ formatTime(task.finishedAt) }}</span>
                <span>公里数：{{ task.distance || 0 }} km</span>
              </div>
              <div v-if="task.status === 'assigned'" class="driver-actions">
                <button class="primary-btn" @click="acceptTask(task)">接受任务</button>
                <textarea v-model="driverTaskForm(task).rejectReason" rows="2" placeholder="拒绝原因，例如车辆故障、现场不具备条件"></textarea>
                <button class="ghost-btn" @click="rejectTask(task)">拒绝任务</button>
              </div>
              <div v-else-if="['accepted', 'to_origin', 'arrived_origin', 'loading', 'transporting', 'arrived_dest', 'unloading'].includes(task.status)" class="driver-actions">
                <p class="form-note">车辆轨迹已持续写入数据库，点击完成后自动汇总本任务公里数。</p>
                <button class="primary-btn" @click="completeTask(task)">完成任务</button>
              </div>
              <FactoryMap
                class="driver-task-map"
                :vehicles="task.assignedForklift ? [task.assignedForklift] : []"
                :points="taskMapPoints(task)"
                base-mode="satellite"
                :show-labels="false"
                :scale-meters="basemap.scaleMeters"
                :meters-per-unit="basemap.metersPerUnit"
              />
              <p v-if="task.status === 'completed'" class="form-note">任务已完成，已进入司机工作报表。</p>
            </article>
            <article v-if="!filteredDriverTasks.length" class="empty-state">当前筛选条件下没有派给你的任务。</article>
          </div>
        </section>
      </section>

      <section v-if="activeView === 'users'" class="work-grid user-work-grid">
        <form class="panel form-panel" @submit.prevent="saveUser">
          <div class="panel-title">
            <div>
              <h3>{{ editingUserId ? '修改系统用户' : '新增系统用户' }}</h3>
              <span>只保留管理员和叉车司机两类账号，管理员拥有全部调度与配置权限。</span>
            </div>
            <button v-if="editingUserId" class="ghost-btn" type="button" @click="resetUserForm">取消编辑</button>
          </div>
          <div class="form-grid">
            <label>账号<input v-model="userForm.username" :disabled="!!editingUserId" /></label>
            <label>初始密码<input v-model="userForm.password" /></label>
            <label>姓名<input v-model="userForm.name" /></label>
            <label>角色<select v-model="userForm.role" :disabled="!!editingUserId"><option value="driver">叉车司机</option><option value="admin">管理员</option></select></label>
            <label>工号<input v-model="userForm.employeeNo" :disabled="userForm.role !== 'driver'" /></label>
            <label>班组<input v-model="userForm.team" /></label>
            <label>手机号<input v-model="userForm.phone" /></label>
            <label>企业微信UserID<input v-model="userForm.wecomUserId" /></label>
            <label>状态<select v-model="userForm.status"><option value="active">active</option><option value="disabled">disabled</option></select></label>
          </div>
          <button class="primary-btn" type="submit">{{ editingUserId ? '保存修改' : '新增用户' }}</button>
        </form>
        <section class="panel">
          <div class="panel-title"><h3>账号列表</h3><span>{{ filteredUsers.length }} / {{ users.length }} 个账号</span></div>
          <div class="list-filter-bar">
            <label>角色<select v-model="userFilters.role"><option value="all">全部角色</option><option v-for="role in userRoleOptions.filter((item) => item !== 'all')" :key="role" :value="role">{{ role }}</option></select></label>
            <label>状态<select v-model="userFilters.status"><option value="all">全部状态</option><option v-for="status in userStatusOptions.filter((item) => item !== 'all')" :key="status" :value="status">{{ status }}</option></select></label>
            <label>关键词<input v-model.trim="userFilters.keyword" placeholder="账号、姓名、班组、企微" /></label>
          </div>
          <div class="table-wrap table-wrap--medium">
            <table>
              <thead><tr><th>账号</th><th>姓名</th><th>角色</th><th>班组/部门</th><th>企业微信</th><th>状态</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="account in filteredUsers" :key="account.id">
                  <td><strong>{{ account.username }}</strong></td>
                  <td>{{ account.name }}</td>
                  <td><span class="status">{{ account.role }}</span></td>
                  <td>{{ account.team || account.department }}</td>
                  <td>{{ account.wecomUserId || '-' }}</td>
                  <td>{{ account.status }}</td>
                  <td class="row-actions">
                    <button class="mini-btn" @click="editUser(account)">修改</button>
                    <button class="mini-btn" :disabled="account.username === 'admin' || account.status === 'disabled'" @click="deleteUser(account)">删除</button>
                  </td>
                </tr>
              </tbody>
            </table>
            <div v-if="!filteredUsers.length" class="empty-state">当前筛选条件下没有账号</div>
          </div>
        </section>
      </section>

      <section v-if="activeView === 'driverReports'" class="view-stack">
        <section class="panel">
          <div class="panel-title">
            <div>
              <h3>司机工作报表</h3>
              <span>按司机统计日、周、月、季度、年度任务数、运送公里数、作业时长。</span>
            </div>
            <div class="report-actions">
              <button class="ghost-btn" type="button" @click="exportDriverReport">导出数据</button>
              <select class="period-select" v-model="driverReportPeriod" @change="loadDriverReport">
                <option value="day">本日</option>
                <option value="week">本周</option>
                <option value="month">本月</option>
                <option value="quarter">本季度</option>
                <option value="year">本年</option>
              </select>
            </div>
          </div>
          <div class="driver-report-summary">
            <div>
              <span>完成任务</span>
              <strong>{{ driverReportTotals.taskCount }}</strong>
            </div>
            <div>
              <span>总公里数</span>
              <strong>{{ driverReportTotals.totalDistance }} km</strong>
            </div>
            <div>
              <span>作业时长</span>
              <strong>{{ driverReportTotals.totalMinutes }} 分钟</strong>
            </div>
            <div>
              <span>有任务司机</span>
              <strong>{{ driverReportTotals.activeDrivers }}</strong>
            </div>
          </div>
        </section>

        <section class="driver-chart-grid">
          <section class="panel">
            <div class="panel-title">
              <div>
                <h3>任务完成排行</h3>
                <span>按当前周期统计每位司机完成任务量。</span>
              </div>
            </div>
            <div ref="driverTaskChartEl" class="echart-box"></div>
          </section>
          <section class="panel">
            <div class="panel-title">
              <div>
                <h3>公里数与作业时长</h3>
                <span>用于识别工作量分布和长耗时任务。</span>
              </div>
            </div>
            <div ref="driverDistanceChartEl" class="echart-box"></div>
          </section>
        </section>

        <section class="panel driver-report-table">
          <div class="panel-title">
            <div>
              <h3>司机明细</h3>
              <span>{{ periodLabel(driverReport.period) }}：{{ driverReport.start }} 至 {{ driverReport.end }}</span>
            </div>
          </div>
          <div class="list-filter-bar">
            <label>班组<select v-model="driverReportFilters.team"><option value="all">全部班组</option><option v-for="team in driverReportTeamOptions.filter((item) => item !== 'all')" :key="team" :value="team">{{ team }}</option></select></label>
            <label>关键词<input v-model.trim="driverReportFilters.keyword" placeholder="司机姓名、工号、班组" /></label>
            <span>显示 {{ filteredDriverReportRows.length }} / {{ driverReport.rows.length }} 名司机</span>
          </div>
          <div class="table-wrap table-wrap--medium">
            <table>
              <thead><tr><th>司机</th><th>班组</th><th>完成任务</th><th>总公里数</th><th>作业时长</th><th>单均公里</th></tr></thead>
              <tbody>
                <tr v-for="row in filteredDriverReportRows" :key="row.driverId">
                  <td><strong>{{ row.name }}</strong><small>{{ row.employeeNo }}</small></td>
                  <td>{{ row.team }}</td>
                  <td>{{ row.taskCount }}</td>
                  <td>{{ row.totalDistance }} km</td>
                  <td>{{ row.totalMinutes }} 分钟</td>
                  <td>{{ row.avgDistance }} km</td>
                </tr>
              </tbody>
            </table>
            <div v-if="!filteredDriverReportRows.length" class="empty-state">当前筛选条件下没有司机报表</div>
          </div>
        </section>
      </section>

      <section v-if="activeView === 'alerts'" class="work-grid alert-work-grid">
        <section class="panel">
          <div class="panel-title">
            <h3>异常闭环中心</h3>
            <span>识别规则、自动推送、责任人处置、结果确认、报表归档</span>
          </div>
          <div class="alert-toolbar">
            <div class="alert-filter-row">
              <label>状态<select v-model="alertFilters.status"><option value="open">待闭环</option><option value="all">全部</option><option value="closed">已关闭</option></select></label>
              <label>级别<select v-model="alertFilters.severity"><option value="all">全部级别</option><option v-for="severity in alertSeverityOptions.filter((item) => item !== 'all')" :key="severity" :value="severity">{{ severity }}</option></select></label>
              <label>类型<select v-model="alertFilters.type"><option value="all">全部类型</option><option v-for="type in alertTypeOptions.filter((item) => item !== 'all')" :key="type" :value="type">{{ alertTypeLabel(type) }}</option></select></label>
            </div>
            <div class="alert-batch-row">
              <label class="check-row">
                <input type="checkbox" :checked="allFilteredAlertsSelected" :disabled="!closableFilteredAlertIds.length" @change="toggleFilteredAlerts($event.target.checked)" />
                全选当前筛选
              </label>
              <span>当前 {{ filteredAlerts.length }} 条，已选 {{ selectedClosableAlertIds.length }} 条</span>
              <button class="mini-btn" type="button" :disabled="!selectedClosableAlertIds.length" @click="closeSelectedAlerts">批量关闭</button>
            </div>
          </div>
          <div class="alert-scroll">
            <article v-for="alert in filteredAlerts" :key="alert.id" class="alert-card" :class="{ 'alert-card--closed': alert.status !== 'open' }">
              <label class="alert-card-check">
                <input type="checkbox" :checked="selectedAlertIds.includes(alert.id)" :disabled="alert.status !== 'open'" @change="toggleAlertSelection(alert, $event.target.checked)" />
              </label>
              <div class="alert-card-body">
                <div class="alert-meta">
                  <b :class="`severity severity--${alert.severity}`">{{ alert.severity }}</b>
                  <span class="status-pill">{{ alertStatusLabel(alert.status) }}</span>
                  <span>{{ alertTypeLabel(alert.alertType) }}</span>
                  <span>{{ formatTime(alert.createdAt) }}</span>
                </div>
                <strong>{{ alert.title }}</strong>
                <p>{{ alert.message }}</p>
                <span>{{ alert.suggestion }}</span>
              </div>
              <button class="mini-btn" :disabled="alert.status !== 'open'" @click="closeAlert(alert)">关闭</button>
            </article>
            <div v-if="!filteredAlerts.length" class="empty-state">当前筛选条件下没有异常记录</div>
          </div>
        </section>
        <section class="panel">
          <div class="panel-title"><h3>日报与运力分析</h3></div>
          <div class="report-grid">
            <article class="report-card"><span>今日任务</span><strong>{{ report.taskTotal }}</strong></article>
            <article class="report-card"><span>已完成</span><strong>{{ report.completed }}</strong></article>
            <article class="report-card"><span>异常</span><strong>{{ report.abnormal }}</strong></article>
            <article class="report-card"><span>平均响应</span><strong>{{ report.avgResponseMinutes }} 分钟</strong></article>
          </div>
          <h4>司机负荷</h4>
          <div class="compact-list report-workload-list">
            <article v-for="driver in report.driverWorkload" :key="driver.name" class="compact-item">
              <div><strong>{{ driver.name }}</strong><span>{{ driver.team }} · {{ driver.workingMinutes }} 分钟</span></div>
              <div class="score-bar score-bar--small"><span :style="{ width: `${driver.workloadScore}%` }"></span></div>
            </article>
          </div>
        </section>
      </section>
    </main>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, GraphicComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import FactoryMap from './components/FactoryMap.vue'
import { api, getToken, setToken } from './api'

echarts.use([BarChart, LineChart, GridComponent, GraphicComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const token = ref(getToken())
const user = ref(JSON.parse(localStorage.getItem('dispatch_user') || 'null'))
const loading = ref(false)
const errorMessage = ref('')
const activeView = ref('overview')
const sidebarHidden = ref(false)
const selectedVehicle = ref(null)
const selectedPoint = ref(null)
const recommendation = ref(null)
const ruleFilter = ref('all')
const ruleSearch = ref('')
const alertFilters = reactive({ status: 'open', severity: 'all', type: 'all' })
const selectedAlertIds = ref([])
const taskFilters = reactive({ status: 'all', priority: 'all', keyword: '' })
const pointFilters = reactive({ type: 'all', status: 'enabled', keyword: '' })
const vehicleFilters = reactive({ status: 'all', powerType: 'all', keyword: '' })
const scheduleFilters = reactive({ status: 'all', keyword: '' })
const bindingFilters = reactive({ keyword: '' })
const userFilters = reactive({ role: 'all', status: 'all', keyword: '' })
const driverReportFilters = reactive({ team: 'all', keyword: '' })
const driverTaskFilters = reactive({ status: 'all', keyword: '' })
const driverForkliftFilters = reactive({ powerType: 'all', keyword: '' })
const draftPoint = ref(null)
const mapEditMode = ref('point')
const activeCalibrationKey = ref('nw')
const nowText = ref(new Date().toLocaleString())
const dispatchMode = ref('auto')
const taskLocationMode = ref('select')
const activeTaskMapTarget = ref('origin')
const editingUserId = ref(null)
const pointEditId = ref(null)
const editingVehicleId = ref(null)
const editingAssignmentId = ref(null)

const loginForm = reactive({ username: 'admin', password: '123456' })
const overview = reactive({ metrics: {}, vehicles: [], tasks: [], alerts: [], mapPoints: [], driverGantt: { date: '', rows: [] } })
const tasks = ref([])
const driverTasks = ref([])
const rules = ref([])
const mapPoints = ref([])
const calibrationReady = ref(false)
const calibrationPoints = ref(defaultCalibrationPoints())
const drivers = ref([])
const vehicles = ref([])
const users = ref([])
const basemap = reactive({ scaleMeters: 50, metersPerUnit: 6.5 })
const schedules = reactive({ shiftTemplates: [], assignments: [], bindings: [] })
const alerts = ref([])
const report = reactive({ taskTotal: 0, completed: 0, abnormal: 0, avgResponseMinutes: 0, driverWorkload: [] })
const driverReportPeriod = ref('week')
const driverReport = reactive({ period: 'week', start: '', end: '', rows: [] })
const driverHomeReportPeriod = ref('week')
const driverHomeReport = reactive({ period: 'week', start: '', end: '', rows: [] })
const driverTaskChartEl = ref(null)
const driverDistanceChartEl = ref(null)
const driverHomeTaskChartEl = ref(null)
const driverHomeDistanceChartEl = ref(null)

const taskForm = reactive({
  originPointId: '',
  destPointId: '',
  cargoType: '生产转运物料',
  estimatedWeight: 1200,
  palletCount: 2,
  priority: 'B',
  note: '',
})

const taskMapDraft = reactive({
  origin: null,
  dest: null,
})

const pointForm = reactive({
  name: '新增取放点',
  pointType: 'pickup',
  area: '自定义区域',
  x: 50,
  y: 50,
  lat: '',
  lng: '',
  geofenceRadius: 5,
  contact: '',
})

const ruleForm = reactive({
  name: '优先派 FLC-001 到北侧仓储区',
  category: 'manual',
  ruleType: 'custom_boost',
  priority: 210,
  weight: 0,
  conditionJsonText: '{\n  "match": {\n    "vehicleCode": "FLC-001",\n    "originArea": "北侧仓储区"\n  }\n}',
  actionJsonText: '{\n  "scoreBoost": 12\n}',
  description: '示例：当起点在北侧仓储区时，提高指定车辆的推荐分。',
})

const bindingForm = reactive({
  driverId: '',
  forkliftId: '',
  shiftCode: 'DAY',
  bindMethod: 'manual',
})

const vehicleForm = reactive({
  code: '',
  plateNo: '',
  model: '3T 电动平衡重',
  powerType: 'electric',
  tonnage: 3,
  status: 'idle',
  batteryLevel: 90,
  fuelLevel: 0,
  online: true,
  currentArea: '自定义区域',
  x: 50,
  y: 50,
  note: '',
})

const scheduleForm = reactive({
  shiftDate: new Date().toISOString().slice(0, 10),
  shiftCode: 'DAY',
  driverId: '',
  forkliftId: '',
  area: '全厂',
  status: 'scheduled',
})

const userForm = reactive({
  username: '',
  password: '123456',
  name: '',
  role: 'driver',
  employeeNo: '',
  team: '',
  phone: '',
  wecomUserId: '',
  status: 'active',
})

const driverTaskForms = reactive({})

const nav = computed(() => {
  if (user.value?.role === 'driver') {
    return [
      { key: 'driverHome', label: '司机主页', icon: 'H' },
      { key: 'driverTasks', label: '我的任务', icon: 'D' },
    ]
  }
  if (user.value?.role === 'admin') {
    return [
      { key: 'overview', label: '地图概览', icon: 'M' },
      { key: 'tasks', label: '调度任务', icon: 'T' },
      { key: 'map', label: '取送货点', icon: 'P' },
      { key: 'vehicles', label: '叉车管理', icon: 'V' },
      { key: 'rules', label: '调度规则', icon: 'G' },
      { key: 'schedules', label: '排班绑定', icon: 'S' },
      { key: 'users', label: '账号管理', icon: 'U' },
      { key: 'driverReports', label: '司机报表', icon: 'R' },
      { key: 'alerts', label: '异常报表', icon: 'A' },
    ]
  }
  return []
})

const currentTitle = computed(() => nav.value.find((item) => item.key === activeView.value)?.label || '调度平台')

const kpiCards = computed(() => [
  { label: '今日任务', value: overview.metrics.totalTasks || 0, hint: `完成率 ${overview.metrics.completionRate || 0}%` },
  { label: '待派任务', value: overview.metrics.pendingTasks || 0, hint: '待审核/待派单' },
  { label: '执行中', value: overview.metrics.activeTasks || 0, hint: '已派单到卸货中' },
  { label: '可用叉车', value: overview.metrics.usableForklifts || 0, hint: `在线 ${overview.metrics.onlineForklifts || 0} 台` },
  { label: '平均电量', value: `${overview.metrics.avgBattery || 0}%`, hint: '低电自动降权' },
  { label: '开放异常', value: overview.metrics.openAlerts || 0, hint: '需闭环处理' },
])

const ganttHours = [0, 4, 8, 12, 16, 20, 24]

const pendingTasks = computed(() =>
  overview.tasks.filter((task) => ['pending_review', 'pending_dispatch', 'exception'].includes(task.status)).slice(0, 6),
)

const transportPoints = computed(() =>
  overview.mapPoints.filter(
    (point) => point.enabled !== false && !point.temporary && !['lora', 'maintenance'].includes(point.pointType),
  ),
)

const taskMapFormPoints = computed(() => {
  const draftPoints = []
  if (taskMapDraft.origin) {
    draftPoints.push({
      ...taskMapDraft.origin,
      id: 'task-draft-origin',
      name: '地图取货点',
      area: '本次任务',
      pointType: 'pickup',
      active: activeTaskMapTarget.value === 'origin',
    })
  }
  if (taskMapDraft.dest) {
    draftPoints.push({
      ...taskMapDraft.dest,
      id: 'task-draft-dest',
      name: '地图送货点',
      area: '本次任务',
      pointType: 'dropoff',
      active: activeTaskMapTarget.value === 'dest',
    })
  }
  return [...transportPoints.value, ...draftPoints]
})

function matchesKeyword(fields, keyword) {
  const text = (keyword || '').trim().toLowerCase()
  if (!text) return true
  return fields.some((field) => String(field ?? '').toLowerCase().includes(text))
}

const taskStatusOptions = computed(() => ['all', ...new Set(tasks.value.map((task) => task.status).filter(Boolean))])
const taskPriorityOptions = computed(() => ['all', ...new Set(tasks.value.map((task) => task.priority).filter(Boolean))])
const filteredTasks = computed(() =>
  tasks.value.filter((task) => {
    const statusOk = taskFilters.status === 'all' || task.status === taskFilters.status
    const priorityOk = taskFilters.priority === 'all' || task.priority === taskFilters.priority
    const keywordOk = matchesKeyword(
      [task.taskNo, task.originLabel, task.destLabel, task.cargoType, task.assignedForklift?.code, task.assignedDriver?.name],
      taskFilters.keyword,
    )
    return statusOk && priorityOk && keywordOk
  }),
)

const pointTypeOptions = computed(() => ['all', ...new Set(mapPoints.value.map((point) => point.pointType).filter(Boolean))])
const filteredMapPoints = computed(() =>
  mapPoints.value.filter((point) => {
    const typeOk = pointFilters.type === 'all' || point.pointType === pointFilters.type
    const statusOk =
      pointFilters.status === 'all' ||
      (pointFilters.status === 'enabled' && point.enabled !== false) ||
      (pointFilters.status === 'disabled' && point.enabled === false)
    const keywordOk = matchesKeyword([point.name, point.area, point.contact, point.lat, point.lng], pointFilters.keyword)
    return typeOk && statusOk && keywordOk
  }),
)

const vehicleStatusOptions = computed(() => ['all', ...new Set(vehicles.value.map((vehicle) => vehicle.status).filter(Boolean))])
const vehiclePowerOptions = computed(() => ['all', ...new Set(vehicles.value.map((vehicle) => vehicle.powerType).filter(Boolean))])
const filteredVehicles = computed(() =>
  vehicles.value.filter((vehicle) => {
    const statusOk = vehicleFilters.status === 'all' || vehicle.status === vehicleFilters.status
    const powerOk = vehicleFilters.powerType === 'all' || vehicle.powerType === vehicleFilters.powerType
    const keywordOk = matchesKeyword(
      [vehicle.code, vehicle.plateNo, vehicle.model, vehicle.currentArea, vehicle.driver?.name],
      vehicleFilters.keyword,
    )
    return statusOk && powerOk && keywordOk
  }),
)

const ruleCategories = computed(() => ['all', ...new Set(rules.value.map((rule) => rule.category))])
const filteredRules = computed(() => {
  return rules.value.filter((rule) => {
    const categoryOk = ruleFilter.value === 'all' || rule.category === ruleFilter.value
    const keywordOk = matchesKeyword([rule.name, rule.code, rule.category, rule.ruleType, rule.description], ruleSearch.value)
    return categoryOk && keywordOk
  })
})
const scoreRules = computed(() => rules.value.filter((rule) => rule.category === 'score'))

const alertSeverityOptions = computed(() => [
  'all',
  ...new Set(['critical', 'warning', 'info', ...alerts.value.map((alert) => alert.severity).filter(Boolean)]),
])
const alertTypeOptions = computed(() => [
  'all',
  ...new Set([
    'dispatch_failure',
    'low_battery',
    'offline',
    'area_congestion',
    'forklift_request',
    ...alerts.value.map((alert) => alert.alertType).filter(Boolean),
  ]),
])
const filteredAlerts = computed(() =>
  alerts.value.filter((alert) => {
    const statusOk = alertFilters.status === 'all' || alert.status === alertFilters.status
    const severityOk = alertFilters.severity === 'all' || alert.severity === alertFilters.severity
    const typeOk = alertFilters.type === 'all' || alert.alertType === alertFilters.type
    return statusOk && severityOk && typeOk
  }),
)
const closableFilteredAlertIds = computed(() => filteredAlerts.value.filter((alert) => alert.status === 'open').map((alert) => alert.id))
const selectedClosableAlertIds = computed(() => {
  const visibleIds = new Set(closableFilteredAlertIds.value)
  return selectedAlertIds.value.filter((id) => visibleIds.has(id))
})
const allFilteredAlertsSelected = computed(
  () => closableFilteredAlertIds.value.length > 0 && selectedClosableAlertIds.value.length === closableFilteredAlertIds.value.length,
)

const activeBindings = computed(() => schedules.bindings.filter((binding) => binding.status === 'active'))
const filteredActiveBindings = computed(() =>
  activeBindings.value.filter((binding) =>
    matchesKeyword(
      [binding.forklift?.code, binding.driver?.name, binding.driver?.employeeNo, binding.shiftCode, binding.bindMethod],
      bindingFilters.keyword,
    ),
  ),
)
const scheduleStatusOptions = computed(() => ['all', ...new Set(schedules.assignments.map((row) => row.status).filter(Boolean))])
const filteredAssignments = computed(() =>
  schedules.assignments.filter((row) => {
    const statusOk = scheduleFilters.status === 'all' || row.status === scheduleFilters.status
    const keywordOk = matchesKeyword(
      [row.shiftCode, row.driver?.name, row.driver?.employeeNo, row.forklift?.code, row.area],
      scheduleFilters.keyword,
    )
    return statusOk && keywordOk
  }),
)

const userRoleOptions = computed(() => ['all', ...new Set(users.value.map((account) => account.role).filter(Boolean))])
const userStatusOptions = computed(() => ['all', ...new Set(users.value.map((account) => account.status).filter(Boolean))])
const filteredUsers = computed(() =>
  users.value.filter((account) => {
    const roleOk = userFilters.role === 'all' || account.role === userFilters.role
    const statusOk = userFilters.status === 'all' || account.status === userFilters.status
    const keywordOk = matchesKeyword(
      [account.username, account.name, account.team, account.department, account.wecomUserId],
      userFilters.keyword,
    )
    return roleOk && statusOk && keywordOk
  }),
)

const driverReportTeamOptions = computed(() => ['all', ...new Set((driverReport.rows || []).map((row) => row.team).filter(Boolean))])
const filteredDriverReportRows = computed(() =>
  (driverReport.rows || []).filter((row) => {
    const teamOk = driverReportFilters.team === 'all' || row.team === driverReportFilters.team
    const keywordOk = matchesKeyword([row.name, row.employeeNo, row.team], driverReportFilters.keyword)
    return teamOk && keywordOk
  }),
)

const driverReportTotals = computed(() => {
  const rows = filteredDriverReportRows.value
  const taskCount = rows.reduce((sum, row) => sum + Number(row.taskCount || 0), 0)
  const totalDistance = rows.reduce((sum, row) => sum + Number(row.totalDistance || 0), 0)
  const totalMinutes = rows.reduce((sum, row) => sum + Number(row.totalMinutes || 0), 0)

  return {
    taskCount,
    totalDistance: totalDistance.toFixed(1),
    totalMinutes,
    activeDrivers: rows.filter((row) => Number(row.taskCount || 0) > 0).length,
  }
})

const driverReportChartRows = computed(() =>
  [...(driverReport.rows || [])]
    .sort(
      (left, right) =>
        Number(right.taskCount || 0) - Number(left.taskCount || 0) ||
        Number(right.totalDistance || 0) - Number(left.totalDistance || 0),
    )
    .slice(0, 12),
)

const currentDriverId = computed(() => user.value?.driverId || null)
const driverVisibleVehicles = computed(() => (overview.vehicles.length ? overview.vehicles : vehicles.value))
const currentDriverForklift = computed(() =>
  driverVisibleVehicles.value.find((vehicle) => vehicle.driver?.id === currentDriverId.value) || null,
)
const availableForklifts = computed(() =>
  driverVisibleVehicles.value.filter((vehicle) => vehicle.online && vehicle.status === 'idle' && !vehicle.driver),
)
const filteredAvailableForklifts = computed(() =>
  availableForklifts.value.filter((vehicle) => {
    const powerOk = driverForkliftFilters.powerType === 'all' || vehicle.powerType === driverForkliftFilters.powerType
    const keywordOk = matchesKeyword([vehicle.code, vehicle.model, vehicle.currentArea, vehicle.powerType], driverForkliftFilters.keyword)
    return powerOk && keywordOk
  }),
)
const driverMapVehicles = computed(() => {
  const selected = currentDriverForklift.value ? [currentDriverForklift.value] : []
  const available = filteredAvailableForklifts.value.filter((vehicle) => vehicle.id !== currentDriverForklift.value?.id)
  return [...selected, ...available]
})
const driverIsOnline = computed(() => user.value?.shiftStatus === 'on_shift')
const driverHomeRow = computed(
  () =>
    driverHomeReport.rows?.[0] || {
      taskCount: 0,
      totalDistance: 0,
      totalMinutes: 0,
      avgDistance: 0,
      completedTasks: [],
    },
)
const driverHomeCompletedTasks = computed(() => driverHomeRow.value.completedTasks || [])
const driverTaskStatusOptions = computed(() => ['all', ...new Set(driverTasks.value.map((task) => task.status).filter(Boolean))])
const filteredDriverTasks = computed(() =>
  driverTasks.value.filter((task) => {
    const statusOk = driverTaskFilters.status === 'all' || task.status === driverTaskFilters.status
    const keywordOk = matchesKeyword(
      [task.taskNo, task.originLabel, task.destLabel, task.cargoType, task.assignedForklift?.code],
      driverTaskFilters.keyword,
    )
    return statusOk && keywordOk
  }),
)
const driverActiveTasks = computed(() =>
  driverTasks.value.filter((task) =>
    ['assigned', 'accepted', 'to_origin', 'arrived_origin', 'loading', 'transporting', 'arrived_dest', 'unloading'].includes(task.status),
  ),
)

let timer = null
let driverTaskChart = null
let driverDistanceChart = null
let driverHomeTaskChart = null
let driverHomeDistanceChart = null

watch(
  () => [
    activeView.value,
    driverReportChartRows.value
      .map((row) => `${row.driverId}:${row.taskCount}:${row.totalDistance}:${row.totalMinutes}`)
      .join('|'),
  ],
  () => {
    if (activeView.value !== 'driverReports') {
      disposeDriverCharts()
      return
    }
    nextTick(renderDriverCharts)
  },
  { flush: 'post' },
)

watch(
  () => [
    activeView.value,
    driverHomeCompletedTasks.value
      .map((task) => `${task.taskNo}:${task.distance}:${task.minutes}`)
      .join('|'),
  ],
  () => {
    if (activeView.value !== 'driverHome') {
      disposeDriverHomeCharts()
      return
    }
    nextTick(renderDriverHomeCharts)
  },
  { flush: 'post' },
)

watch(
  alertFilters,
  () => {
    selectedAlertIds.value = []
    if (token.value && activeView.value === 'alerts') {
      loadAlerts().catch((err) => {
        errorMessage.value = err.message
      })
    }
  },
  { deep: true },
)

onMounted(async () => {
  window.addEventListener('resize', resizeDriverCharts)
  if (token.value) {
    await restoreSession()
  }
  timer = window.setInterval(() => {
    nowText.value = new Date().toLocaleString()
    if (token.value && ['overview', 'map'].includes(activeView.value)) loadOverview()
    if (token.value && activeView.value === 'driverHome') {
      loadOverview()
      loadVehicles()
      loadDriverTasks()
    }
    if (token.value && activeView.value === 'driverTasks') loadDriverTasks()
    if (token.value && activeView.value === 'alerts') {
      loadAlerts()
      loadReport()
    }
  }, 5000)
})

onUnmounted(() => {
  window.clearInterval(timer)
  window.removeEventListener('resize', resizeDriverCharts)
  disposeDriverCharts()
  disposeDriverHomeCharts()
})

async function login() {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await api.login(loginForm)
    setToken(data.token)
    localStorage.setItem('dispatch_user', JSON.stringify(data.user))
    token.value = data.token
    user.value = data.user
    setDefaultView(true)
    await loadAll()
  } catch (err) {
    errorMessage.value = err.message
  } finally {
    loading.value = false
  }
}

async function restoreSession() {
  errorMessage.value = ''
  try {
    const currentUser = await api.get('/api/auth/me')
    if (!['admin', 'driver'].includes(currentUser.role)) {
      throw new Error('调度员权限已合并到管理员，请使用管理员或司机账号登录。')
    }
    user.value = currentUser
    localStorage.setItem('dispatch_user', JSON.stringify(currentUser))
    setDefaultView(true)
    await loadAll()
  } catch (err) {
    logout()
    errorMessage.value = `登录状态已失效，请重新登录：${err.message}`
  }
}

function logout() {
  setToken('')
  localStorage.removeItem('dispatch_user')
  token.value = ''
  user.value = null
}

async function loadAll() {
  const role = user.value?.role
  if (role === 'driver') {
    await runLoaders([loadBasemap, loadOverview, loadVehicles, loadDriverTasks, loadDriverHomeReport])
    return
  }
  if (role === 'admin') {
    await runLoaders([
      loadOverview,
      loadBasemap,
      loadTasks,
      loadDrivers,
      loadVehicles,
      loadSchedules,
      loadUsers,
      loadDriverReport,
      loadRules,
      loadMapPoints,
      loadAlerts,
      loadReport,
    ])
    return
  }
  throw new Error('调度员权限已合并到管理员，请使用 admin 登录。')
}

async function runLoaders(loaders) {
  const results = await Promise.allSettled(loaders.map((loader) => loader()))
  const failed = results.filter((result) => result.status === 'rejected')
  if (failed.length) {
    throw new Error(failed[0].reason?.message || '部分数据加载失败')
  }
}

async function loadOverview() {
  const data = await api.get('/api/overview')
  Object.assign(overview, data)
  const selectable = data.mapPoints.filter((point) => !point.temporary && !['lora', 'maintenance'].includes(point.pointType))
  if (!taskForm.originPointId && selectable.length >= 2) {
    taskForm.originPointId = selectable[0].id
    taskForm.destPointId = selectable[1].id
  }
}

async function loadBasemap() {
  const data = await api.get('/api/basemap')
  basemap.scaleMeters = data.scaleMeters || 50
  basemap.metersPerUnit = data.metersPerUnit || 6.5
  if (data.calibration) applyCalibration(data.calibration)
}

async function loadTasks() {
  tasks.value = await api.get('/api/tasks')
}

async function loadDriverTasks() {
  driverTasks.value = await api.get('/api/tasks')
}

function taskMapPoints(task) {
  const origin = overview.mapPoints.find((point) => point.id === task.originPointId)
  const destination = overview.mapPoints.find((point) => point.id === task.destPointId)
  return [
    origin && { ...origin, id: `task-${task.id}-origin`, name: `取货：${origin.name}`, pointType: 'pickup' },
    destination && { ...destination, id: `task-${task.id}-dest`, name: `送货：${destination.name}`, pointType: 'dropoff' },
  ].filter(Boolean)
}

async function loadRules() {
  rules.value = await api.get('/api/rules')
}

async function loadMapPoints() {
  mapPoints.value = await api.get('/api/map-points')
}

async function loadDrivers() {
  drivers.value = await api.get('/api/drivers')
}

async function loadVehicles() {
  vehicles.value = await api.get('/api/vehicles')
}

async function loadSchedules() {
  Object.assign(schedules, await api.get('/api/schedules'))
  if (!bindingForm.shiftCode && schedules.shiftTemplates.length) {
    bindingForm.shiftCode = schedules.shiftTemplates[0].code
  }
  if (!scheduleForm.shiftCode && schedules.shiftTemplates.length) {
    scheduleForm.shiftCode = schedules.shiftTemplates[0].code
  }
}

async function loadAlerts() {
  const params = new URLSearchParams()
  params.set('status', alertFilters.status === 'all' ? '' : alertFilters.status)
  if (alertFilters.severity !== 'all') params.set('severity', alertFilters.severity)
  if (alertFilters.type !== 'all') params.set('alertType', alertFilters.type)
  alerts.value = await api.get(`/api/alerts?${params.toString()}`)
  const openIds = new Set(alerts.value.filter((alert) => alert.status === 'open').map((alert) => alert.id))
  selectedAlertIds.value = selectedAlertIds.value.filter((id) => openIds.has(id))
}

async function loadReport() {
  Object.assign(report, await api.get('/api/reports/daily'))
}

async function loadUsers() {
  users.value = await api.get('/api/users')
}

function defaultCalibrationPoints() {
  return [
    { cornerKey: 'nw', label: '西北角', x: 0, y: 0, lat: '', lng: '', enabled: true },
    { cornerKey: 'ne', label: '东北角', x: 100, y: 0, lat: '', lng: '', enabled: true },
    { cornerKey: 'se', label: '东南角', x: 100, y: 100, lat: '', lng: '', enabled: true },
    { cornerKey: 'sw', label: '西南角', x: 0, y: 100, lat: '', lng: '', enabled: true },
  ]
}

function applyCalibration(payload) {
  calibrationReady.value = !!payload.ready
  calibrationPoints.value = (payload.points?.length ? payload.points : defaultCalibrationPoints()).map((point) => ({
    cornerKey: point.cornerKey,
    label: point.label,
    x: Number(point.x ?? 0),
    y: Number(point.y ?? 0),
    lat: point.lat ?? '',
    lng: point.lng ?? '',
    enabled: point.enabled !== false,
  }))
}

async function loadDriverReport() {
  Object.assign(driverReport, await api.get(`/api/reports/drivers?period=${driverReportPeriod.value}`))
  await nextTick()
  renderDriverCharts()
}

async function loadDriverHomeReport() {
  Object.assign(driverHomeReport, await api.get(`/api/reports/me?period=${driverHomeReportPeriod.value}`))
  await nextTick()
  renderDriverHomeCharts()
}

function renderDriverCharts() {
  if (activeView.value !== 'driverReports' || !driverTaskChartEl.value || !driverDistanceChartEl.value) return

  const rows = driverReportChartRows.value
  const labels = rows.map((row) => `${row.name}\n${row.employeeNo}`)
  const taskCounts = rows.map((row) => Number(row.taskCount || 0))
  const distances = rows.map((row) => Number(row.totalDistance || 0))
  const minutes = rows.map((row) => Number(row.totalMinutes || 0))
  const emptyGraphic = rows.length
    ? []
    : {
        type: 'text',
        left: 'center',
        top: 'middle',
        style: { text: '暂无报表数据', fill: '#6f7f7a', fontSize: 14 },
      }

  if (!driverTaskChart) driverTaskChart = echarts.init(driverTaskChartEl.value)
  if (!driverDistanceChart) driverDistanceChart = echarts.init(driverDistanceChartEl.value)

  driverTaskChart.setOption({
    color: ['#1f7a6c'],
    tooltip: { trigger: 'axis' },
    grid: { top: 28, right: 18, bottom: 56, left: 42 },
    xAxis: { type: 'category', data: labels, axisLabel: { interval: 0, lineHeight: 16 } },
    yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#e3ebe8' } } },
    series: [{ name: '完成任务', type: 'bar', data: taskCounts, barMaxWidth: 28 }],
    graphic: emptyGraphic,
  })

  driverDistanceChart.setOption({
    color: ['#bd7b18', '#4568a8'],
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    grid: { top: 46, right: 48, bottom: 56, left: 48 },
    xAxis: { type: 'category', data: labels, axisLabel: { interval: 0, lineHeight: 16 } },
    yAxis: [
      { type: 'value', name: '公里', splitLine: { lineStyle: { color: '#e3ebe8' } } },
      { type: 'value', name: '分钟', splitLine: { show: false } },
    ],
    series: [
      { name: '总公里数', type: 'line', smooth: true, data: distances, areaStyle: { opacity: 0.12 } },
      { name: '作业时长', type: 'bar', yAxisIndex: 1, data: minutes, barMaxWidth: 24 },
    ],
    graphic: emptyGraphic,
  })

  resizeDriverCharts()
}

function renderDriverHomeCharts() {
  if (activeView.value !== 'driverHome' || !driverHomeTaskChartEl.value || !driverHomeDistanceChartEl.value) return

  const rows = driverHomeCompletedTasks.value
  const labels = rows.map((task) => task.taskNo.replace('TASK-', ''))
  const distances = rows.map((task) => Number(task.distance || 0))
  const minutes = rows.map((task) => Number(task.minutes || 0))
  const emptyGraphic = rows.length
    ? []
    : {
        type: 'text',
        left: 'center',
        top: 'middle',
        style: { text: '当前周期暂无完成任务', fill: '#6f7f7a', fontSize: 14 },
      }

  if (!driverHomeTaskChart) driverHomeTaskChart = echarts.init(driverHomeTaskChartEl.value)
  if (!driverHomeDistanceChart) driverHomeDistanceChart = echarts.init(driverHomeDistanceChartEl.value)

  driverHomeTaskChart.setOption({
    color: ['#1f7a6c'],
    tooltip: { trigger: 'axis' },
    grid: { top: 28, right: 18, bottom: 58, left: 42 },
    xAxis: { type: 'category', data: labels, axisLabel: { interval: 0, rotate: labels.length > 5 ? 20 : 0 } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#e3ebe8' } } },
    series: [{ name: '公里数', type: 'bar', data: distances, barMaxWidth: 32 }],
    graphic: emptyGraphic,
  })

  driverHomeDistanceChart.setOption({
    color: ['#bd7b16'],
    tooltip: { trigger: 'axis' },
    grid: { top: 28, right: 18, bottom: 58, left: 42 },
    xAxis: { type: 'category', data: labels, axisLabel: { interval: 0, rotate: labels.length > 5 ? 20 : 0 } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#e3ebe8' } } },
    series: [{ name: '作业时长', type: 'line', smooth: true, data: minutes }],
    graphic: emptyGraphic,
  })

  resizeDriverCharts()
}

function resizeDriverCharts() {
  driverTaskChart?.resize()
  driverDistanceChart?.resize()
  driverHomeTaskChart?.resize()
  driverHomeDistanceChart?.resize()
}

function disposeDriverCharts() {
  driverTaskChart?.dispose()
  driverDistanceChart?.dispose()
  driverTaskChart = null
  driverDistanceChart = null
}

function disposeDriverHomeCharts() {
  driverHomeTaskChart?.dispose()
  driverHomeDistanceChart?.dispose()
  driverHomeTaskChart = null
  driverHomeDistanceChart = null
}

function exportDriverReport() {
  const headers = ['周期', '开始日期', '结束日期', '司机', '工号', '班组', '完成任务', '总公里数(km)', '作业时长(分钟)', '单均公里(km)']
  const rows = (driverReport.rows || []).map((row) => [
    periodLabel(driverReport.period),
    driverReport.start,
    driverReport.end,
    row.name,
    row.employeeNo,
    row.team,
    row.taskCount,
    row.totalDistance,
    row.totalMinutes,
    row.avgDistance,
  ])
  downloadCsv(`司机工作报表_${periodLabel(driverReport.period)}_${new Date().toISOString().slice(0, 10)}.csv`, [headers, ...rows])
}

function downloadCsv(filename, rows) {
  const csv = `\uFEFF${rows.map((row) => row.map(csvCell).join(',')).join('\r\n')}`
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.setTimeout(() => window.URL.revokeObjectURL(url), 0)
}

function csvCell(value) {
  const text = String(value ?? '')
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

function periodLabel(period) {
  return { day: '本日', week: '本周', month: '本月', quarter: '本季度', year: '本年' }[period] || period
}

function setDefaultView(force = false) {
  const keys = nav.value.map((item) => item.key)
  if (force || !keys.includes(activeView.value)) {
    activeView.value = keys[0] || 'overview'
  }
}

function setTaskMapPoint(point) {
  const target = activeTaskMapTarget.value === 'dest' ? 'dest' : 'origin'
  taskMapDraft[target] = {
    sourcePointId: typeof point.id === 'number' ? point.id : null,
    sourceName: point.name || '',
    x: Number(point.x),
    y: Number(point.y),
    lat: point.lat ?? '',
    lng: point.lng ?? '',
  }
  if (target === 'origin' && !taskMapDraft.dest) {
    activeTaskMapTarget.value = 'dest'
  }
}

function selectTaskMapExistingPoint(point) {
  if (point.id === 'task-draft-origin') {
    activeTaskMapTarget.value = 'origin'
    return
  }
  if (point.id === 'task-draft-dest') {
    activeTaskMapTarget.value = 'dest'
    return
  }
  setTaskMapPoint(point)
}

function taskMapLabel(target) {
  const point = taskMapDraft[target]
  if (!point) return '未标记'
  if (point.sourceName) return point.sourceName
  const latLng = point.lat && point.lng ? ` / ${point.lat}, ${point.lng}` : ''
  return `X ${point.x}, Y ${point.y}${latLng}`
}

function resetTaskMapDraft() {
  taskMapDraft.origin = null
  taskMapDraft.dest = null
  activeTaskMapTarget.value = 'origin'
}

async function ensureTaskMapPoint(target) {
  const point = taskMapDraft[target]
  if (!point) {
    throw new Error(target === 'origin' ? '请先在地图上标记取货点。' : '请先在地图上标记送货点。')
  }
  if (point.sourcePointId) return point.sourcePointId
  const isOrigin = target === 'origin'
  const stamp = new Date().toISOString().replace(/[-:T.Z]/g, '').slice(0, 14)
  const created = await api.post('/api/map-points', {
    name: `${isOrigin ? '临时取货点' : '临时送货点'}-${stamp}`,
    pointType: isOrigin ? 'pickup' : 'dropoff',
    area: '任务临时点',
    x: point.x,
    y: point.y,
    lat: point.lat,
    lng: point.lng,
    geofenceRadius: 5,
    contact: '调度',
    temporary: true,
    description: '发布搬运任务地图标点自动生成',
  })
  return created.id
}

async function createTask() {
  errorMessage.value = ''
  const payload = { ...taskForm }
  try {
    if (taskLocationMode.value === 'map') {
      payload.originPointId = await ensureTaskMapPoint('origin')
      payload.destPointId = await ensureTaskMapPoint('dest')
    }
    await api.post('/api/tasks', payload)
  } catch (err) {
    errorMessage.value = err.message
    return
  }
  if (taskLocationMode.value === 'map') resetTaskMapDraft()
  await loadAll()
}

function resetUserForm() {
  editingUserId.value = null
  Object.assign(userForm, {
    username: '',
    password: '123456',
    name: '',
    role: 'driver',
    employeeNo: '',
    team: '',
    phone: '',
    wecomUserId: '',
    status: 'active',
  })
}

function editUser(account) {
  editingUserId.value = account.id
  Object.assign(userForm, {
    username: account.username,
    password: '',
    name: account.name,
    role: account.role,
    employeeNo: account.employeeNo || '',
    team: account.team || '',
    phone: account.phone || '',
    wecomUserId: account.wecomUserId || '',
    status: account.status || 'active',
  })
}

async function saveUser() {
  errorMessage.value = ''
  const payload = { ...userForm }
  if (!payload.password) delete payload.password
  if (editingUserId.value) {
    await api.patch(`/api/users/${editingUserId.value}`, payload)
  } else {
    await api.post('/api/users', payload)
  }
  resetUserForm()
  await loadUsers()
  await loadDrivers()
}

async function deleteUser(account) {
  if (account.username === 'admin') return
  await api.del(`/api/users/${account.id}`)
  resetUserForm()
  await loadUsers()
  await loadDrivers()
  await loadSchedules()
  await loadVehicles()
}

async function previewTask(task) {
  recommendation.value = await api.get(`/api/tasks/${task.id}/recommendations`)
}

async function openManualDispatch(task) {
  dispatchMode.value = 'manual'
  await previewTask(task)
}

async function dispatchTask(task, forkliftId = null) {
  await api.post(`/api/tasks/${task.id}/assign`, forkliftId ? { forkliftId } : {})
  recommendation.value = null
  await loadAll()
}

async function markComplete(task) {
  await api.post(`/api/tasks/${task.id}/status`, { status: 'completed', message: '管理员手动确认完成' })
  await loadAll()
}

async function toggleVehicleLock(vehicle) {
  const status = vehicle.status === 'disabled' ? 'idle' : 'disabled'
  await api.patch(`/api/vehicles/${vehicle.id}`, { status })
  await loadAll()
}

function resetVehicleForm() {
  editingVehicleId.value = null
  Object.assign(vehicleForm, {
    code: '',
    plateNo: '',
    model: '3T 电动平衡重',
    powerType: 'electric',
    tonnage: 3,
    status: 'idle',
    batteryLevel: 90,
    fuelLevel: 0,
    online: true,
    currentArea: '自定义区域',
    x: 50,
    y: 50,
    note: '',
  })
}

function editVehicle(vehicle) {
  editingVehicleId.value = vehicle.id
  Object.assign(vehicleForm, {
    code: vehicle.code,
    plateNo: vehicle.plateNo || '',
    model: vehicle.model || '',
    powerType: vehicle.powerType || 'electric',
    tonnage: vehicle.tonnage || 3,
    status: vehicle.status || 'idle',
    batteryLevel: vehicle.batteryLevel || 0,
    fuelLevel: vehicle.fuelLevel || 0,
    online: vehicle.online !== false,
    currentArea: vehicle.currentArea || '',
    x: vehicle.x || 50,
    y: vehicle.y || 50,
    note: vehicle.note || '',
  })
}

async function saveVehicle() {
  errorMessage.value = ''
  const payload = { ...vehicleForm }
  if (editingVehicleId.value) {
    await api.patch(`/api/vehicles/${editingVehicleId.value}`, payload)
  } else {
    await api.post('/api/vehicles', payload)
  }
  resetVehicleForm()
  await loadVehicles()
  await loadOverview()
}

async function deleteVehicle(vehicle) {
  await api.del(`/api/vehicles/${vehicle.id}`)
  await loadVehicles()
  await loadOverview()
  await loadSchedules()
}

function handleMapClick(point) {
  if (mapEditMode.value === 'calibration') {
    setCalibrationDraft(point)
    return
  }
  setDraftPoint(point)
}

function setDraftPoint(point) {
  draftPoint.value = point
  pointForm.x = point.x
  pointForm.y = point.y
  pointForm.lat = point.lat
  pointForm.lng = point.lng
}

function setCalibrationDraft(point) {
  const corner = calibrationPoints.value.find((item) => item.cornerKey === activeCalibrationKey.value)
  if (!corner) return
  corner.x = point.x
  corner.y = point.y
  corner.lat = point.lat
  corner.lng = point.lng
}

function selectCalibrationPoint(corner) {
  activeCalibrationKey.value = corner.cornerKey
}

function fillPoint(point) {
  selectedPoint.value = point
  pointEditId.value = point.id
  pointForm.name = point.name
  pointForm.pointType = point.pointType
  pointForm.area = point.area
  pointForm.x = point.x
  pointForm.y = point.y
  pointForm.lat = point.lat ?? ''
  pointForm.lng = point.lng ?? ''
  pointForm.geofenceRadius = point.geofenceRadius
  pointForm.contact = point.contact
  draftPoint.value = { x: point.x, y: point.y, lat: point.lat ?? '', lng: point.lng ?? '' }
}

function resetPointForm() {
  pointEditId.value = null
  draftPoint.value = null
  Object.assign(pointForm, {
    name: '新增取放点',
    pointType: 'pickup',
    area: '自定义区域',
    x: 50,
    y: 50,
    lat: '',
    lng: '',
    geofenceRadius: 5,
    contact: '',
  })
}

async function savePoint() {
  if (pointEditId.value) {
    await api.patch(`/api/map-points/${pointEditId.value}`, pointForm)
  } else {
    await api.post('/api/map-points', pointForm)
  }
  resetPointForm()
  await loadMapPoints()
  await loadOverview()
}

async function saveCalibration() {
  const data = await api.put('/api/basemap/calibration', { points: calibrationPoints.value })
  applyCalibration(data)
  await loadOverview()
}

async function convertPointGpsToXY() {
  if (pointForm.lat === '' || pointForm.lng === '') {
    errorMessage.value = '请先填写点位纬度和经度。'
    return
  }
  const mapped = await api.post('/api/basemap/convert', {
    lat: pointForm.lat,
    lng: pointForm.lng,
  })
  pointForm.x = mapped.x
  pointForm.y = mapped.y
  draftPoint.value = { x: mapped.x, y: mapped.y }
  errorMessage.value = ''
}

async function deletePoint(point) {
  if (!point.enabled) return
  await api.del(`/api/map-points/${point.id}`)
  await loadMapPoints()
  await loadOverview()
}

async function createRule() {
  const body = {
    name: ruleForm.name,
    category: ruleForm.category,
    ruleType: ruleForm.ruleType,
    priority: ruleForm.priority,
    weight: ruleForm.weight,
    conditionJson: JSON.parse(ruleForm.conditionJsonText || '{}'),
    actionJson: JSON.parse(ruleForm.actionJsonText || '{}'),
    description: ruleForm.description,
  }
  await api.post('/api/rules', body)
  await loadRules()
}

async function toggleRule(rule) {
  await api.patch(`/api/rules/${rule.id}`, { enabled: !rule.enabled })
  await loadRules()
}

async function saveRuleWeight(rule) {
  await api.patch(`/api/rules/${rule.id}`, { weight: Number(rule.weight || 0) })
  await loadRules()
}

async function deleteRule(rule) {
  if (!rule.editable) return
  await api.del(`/api/rules/${rule.id}`)
  await loadRules()
}

function prefillBinding(row) {
  bindingForm.driverId = row.driver?.id || ''
  bindingForm.forkliftId = row.forklift?.id || ''
  bindingForm.shiftCode = row.shiftCode || bindingForm.shiftCode || 'DAY'
  bindingForm.bindMethod = 'manual'
}

function resetScheduleForm() {
  editingAssignmentId.value = null
  Object.assign(scheduleForm, {
    shiftDate: new Date().toISOString().slice(0, 10),
    shiftCode: schedules.shiftTemplates[0]?.code || 'DAY',
    driverId: '',
    forkliftId: '',
    area: '全厂',
    status: 'scheduled',
  })
}

function editAssignment(row) {
  editingAssignmentId.value = row.id
  Object.assign(scheduleForm, {
    shiftDate: row.shiftDate || new Date().toISOString().slice(0, 10),
    shiftCode: row.shiftCode || 'DAY',
    driverId: row.driver?.id || '',
    forkliftId: row.forklift?.id || '',
    area: row.area || '全厂',
    status: row.status || 'scheduled',
  })
}

async function saveAssignment() {
  if (!scheduleForm.driverId) {
    errorMessage.value = '请选择司机后再保存排班'
    return
  }
  errorMessage.value = ''
  const payload = { ...scheduleForm }
  if (editingAssignmentId.value) {
    await api.patch(`/api/schedules/assignments/${editingAssignmentId.value}`, payload)
  } else {
    await api.post('/api/schedules/assignments', payload)
  }
  resetScheduleForm()
  await loadSchedules()
  await loadDrivers()
}

async function deleteAssignment(row) {
  await api.del(`/api/schedules/assignments/${row.id}`)
  if (editingAssignmentId.value === row.id) resetScheduleForm()
  await loadSchedules()
}

async function bindVehicle() {
  if (!bindingForm.driverId || !bindingForm.forkliftId) {
    errorMessage.value = '请选择司机和车辆后再保存绑定'
    return
  }
  errorMessage.value = ''
  await api.post('/api/bindings', {
    driverId: bindingForm.driverId,
    forkliftId: bindingForm.forkliftId,
    shiftCode: bindingForm.shiftCode,
    bindMethod: bindingForm.bindMethod,
  })
  await loadAll()
}

async function closeBinding(binding) {
  await api.post(`/api/bindings/${binding.id}/close`, {})
  await loadAll()
}

async function toggleDriverOnline() {
  errorMessage.value = ''
  const shiftStatus = driverIsOnline.value ? 'off_shift' : 'on_shift'
  try {
    const updatedUser = await api.patch('/api/driver/status', { shiftStatus })
    user.value = updatedUser
    localStorage.setItem('dispatch_user', JSON.stringify(updatedUser))
    await loadAll()
  } catch (err) {
    errorMessage.value = err.message
  }
}

async function requestForklift(vehicle) {
  errorMessage.value = ''
  try {
    await api.post('/api/driver/forklift-requests', { forkliftId: vehicle.id })
    errorMessage.value = `已提交 ${vehicle.code} 的叉车申请，等待管理员确认绑定。`
    await loadOverview()
    await loadVehicles()
  } catch (err) {
    errorMessage.value = err.message
  }
}

function driverTaskForm(task) {
  if (!driverTaskForms[task.id]) {
    driverTaskForms[task.id] = { rejectReason: '', distance: task.distance || '' }
  }
  return driverTaskForms[task.id]
}

async function acceptTask(task) {
  await api.post(`/api/tasks/${task.id}/driver-accept`, {})
  await loadDriverTasks()
  await loadOverview()
}

async function rejectTask(task) {
  const form = driverTaskForm(task)
  if (!form.rejectReason.trim()) {
    errorMessage.value = '拒绝任务必须填写原因'
    return
  }
  errorMessage.value = ''
  await api.post(`/api/tasks/${task.id}/driver-reject`, { reason: form.rejectReason })
  await loadDriverTasks()
  await loadOverview()
}

async function completeTask(task) {
  errorMessage.value = ''
  await api.post(`/api/tasks/${task.id}/driver-complete`, {})
  await loadDriverTasks()
  await loadDriverHomeReport()
  await loadOverview()
}

function toggleAlertSelection(alert, checked) {
  if (alert.status !== 'open') return
  const ids = new Set(selectedAlertIds.value)
  if (checked) {
    ids.add(alert.id)
  } else {
    ids.delete(alert.id)
  }
  selectedAlertIds.value = [...ids]
}

function toggleFilteredAlerts(checked) {
  if (checked) {
    selectedAlertIds.value = [...new Set([...selectedAlertIds.value, ...closableFilteredAlertIds.value])]
    return
  }
  const visibleIds = new Set(closableFilteredAlertIds.value)
  selectedAlertIds.value = selectedAlertIds.value.filter((id) => !visibleIds.has(id))
}

async function closeSelectedAlerts() {
  const ids = selectedClosableAlertIds.value
  if (!ids.length) return
  await api.post('/api/alerts/batch-close', {
    ids,
    message: `管理员批量闭环 ${ids.length} 条异常`,
  })
  selectedAlertIds.value = []
  await Promise.all([loadAlerts(), loadOverview(), loadReport()])
}

async function closeAlert(alert) {
  await api.post(`/api/alerts/${alert.id}/close`, { message: '管理员已处理并确认闭环' })
  selectedAlertIds.value = selectedAlertIds.value.filter((id) => id !== alert.id)
  await Promise.all([loadAlerts(), loadOverview(), loadReport()])
}

function alertStatusLabel(status) {
  return { open: '待闭环', closed: '已关闭', processing: '处理中' }[status] || status
}

function alertTypeLabel(type) {
  const dict = {
    low_battery: '低电量',
    offline: '设备离线',
    area_congestion: '区域拥堵',
    dispatch_failure: '派单失败',
    forklift_request: '司机申请叉车',
  }
  return dict[type] || type
}

function formatTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function ganttSegmentStyle(segment) {
  const start = Math.max(0, Math.min(1440, Number(segment.startMinutes || 0)))
  const end = Math.max(start + 4, Math.min(1440, Number(segment.endMinutes || start + 5)))
  return {
    left: `${(start / 1440) * 100}%`,
    width: `${Math.max(0.8, ((end - start) / 1440) * 100)}%`,
  }
}

function canDispatch(task) {
  return ['pending_review', 'pending_dispatch'].includes(task.status)
}

function pointTypeLabel(type) {
  const dict = {
    pickup: '取货点',
    dropoff: '送货点',
    dock: '装卸口',
    charging: '充电区',
    maintenance: '维修点',
    parking: '待命区',
    lora: 'LoRa点',
    handover: '交接点',
    route: '通行点',
  }
  return dict[type] || type
}

function powerTypeLabel(type) {
  const dict = {
    electric: '电动叉车',
    diesel: '柴油叉车',
    gasoline: '汽油叉车',
    lpg: '液化气叉车',
  }
  return dict[type] || type
}
</script>
