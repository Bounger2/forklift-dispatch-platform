import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ActivityIndicator,
  Alert,
  ImageBackground,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  RefreshControl,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native'
import { MaterialCommunityIcons } from '@expo/vector-icons'
import * as FileSystem from 'expo-file-system'
import * as Sharing from 'expo-sharing'

import { API_BASE, api, restoreToken, setToken } from './src/api'
import { colors, shadow } from './src/theme'

const emptyTaskForm = {
  originPointId: '',
  destPointId: '',
  cargoType: '生产转运物料',
  estimatedWeight: '1200',
  palletCount: '2',
  priority: 'B',
  note: '',
}

const emptyPointForm = {
  name: '',
  pointType: 'pickup',
  area: '厂区',
  x: '50',
  y: '50',
  lat: '',
  lng: '',
  geofenceRadius: '5',
  contact: '',
  temporary: false,
}

const emptyVehicleForm = {
  code: '',
  plateNo: '',
  model: '3T 平衡重叉车',
  powerType: 'electric',
  tonnage: '3',
  status: 'idle',
  batteryLevel: '90',
  fuelLevel: '0',
  online: true,
  currentArea: '厂区',
  x: '50',
  y: '50',
  note: '',
}

const emptyUserForm = {
  username: '',
  password: '123456',
  name: '',
  role: 'driver',
  employeeNo: '',
  phone: '',
  team: '',
  department: '物流部',
  wecomUserId: '',
  status: 'active',
}

const emptyRuleForm = {
  name: '',
  category: 'priority',
  ruleType: 'custom',
  priority: '100',
  weight: '10',
  enabled: true,
  description: '',
}

function fmtTime(value) {
  if (!value) return '-'
  return String(value).replace('T', ' ').slice(0, 19)
}

function statusLabel(status) {
  const map = {
    pending_dispatch: '待派单',
    assigned: '待接收',
    accepted: '执行中',
    completed: '已完成',
    exception: '异常',
    idle: '空闲',
    executing: '执行',
    disabled: '停用',
  }
  return map[status] || status || '-'
}

function priorityColor(priority) {
  if (priority === 'S' || priority === 'A') return colors.danger
  if (priority === 'B') return colors.primary
  return '#697a76'
}

function makeOptions(rows, labelKey = 'name') {
  return rows.map((row) => ({ label: row[labelKey] || row.code || row.username, value: String(row.id) }))
}

export default function App() {
  const [booting, setBooting] = useState(true)
  const [user, setUser] = useState(null)
  const [loginForm, setLoginForm] = useState({ username: 'admin', password: '123456' })
  const [tab, setTab] = useState('overview')
  const [adminPanel, setAdminPanel] = useState('points')
  const [reportPeriod, setReportPeriod] = useState('day')
  const [refreshing, setRefreshing] = useState(false)
  const [errorText, setErrorText] = useState('')

  const [overview, setOverview] = useState({ metrics: {}, vehicles: [], tasks: [], alerts: [], mapPoints: [], driverGantt: [] })
  const [tasks, setTasks] = useState([])
  const [points, setPoints] = useState([])
  const [vehicles, setVehicles] = useState([])
  const [drivers, setDrivers] = useState([])
  const [rules, setRules] = useState([])
  const [schedules, setSchedules] = useState({ shiftTemplates: [], assignments: [], bindings: [] })
  const [users, setUsers] = useState([])
  const [alerts, setAlerts] = useState([])
  const [driverReport, setDriverReport] = useState({ rows: [], period: 'day' })
  const [myReport, setMyReport] = useState({ rows: [] })

  const isAdmin = user?.role === 'admin'
  const isDriver = user?.role === 'driver'

  const loadCore = useCallback(async () => {
    if (!user) return
    setErrorText('')
    const [overviewData, taskData, pointData, vehicleData, driverData] = await Promise.all([
      api.get('/api/overview'),
      api.get('/api/tasks'),
      api.get('/api/map-points'),
      api.get('/api/vehicles'),
      api.get('/api/drivers'),
    ])
    setOverview(overviewData)
    setTasks(taskData)
    setPoints(pointData)
    setVehicles(vehicleData)
    setDrivers(driverData)

    if (isAdmin) {
      const [ruleData, scheduleData, userData, alertData, reportData] = await Promise.all([
        api.get('/api/rules'),
        api.get('/api/schedules'),
        api.get('/api/users'),
        api.get('/api/alerts?status=open'),
        api.get(`/api/reports/drivers?period=${reportPeriod}`),
      ])
      setRules(ruleData)
      setSchedules(scheduleData)
      setUsers(userData)
      setAlerts(alertData)
      setDriverReport(reportData)
    }

    if (isDriver) {
      setMyReport(await api.get(`/api/reports/me?period=${reportPeriod}`))
    }
  }, [isAdmin, isDriver, reportPeriod, user])

  useEffect(() => {
    async function boot() {
      try {
        const token = await restoreToken()
        if (token) {
          const currentUser = await api.get('/api/auth/me')
          setUser(currentUser)
          setTab(currentUser.role === 'driver' ? 'driverHome' : 'overview')
        }
      } catch {
        await setToken('')
      } finally {
        setBooting(false)
      }
    }
    boot()
  }, [])

  useEffect(() => {
    if (!user) return
    loadCore().catch((err) => setErrorText(err.message))
    const timer = setInterval(() => loadCore().catch(() => {}), 5000)
    return () => clearInterval(timer)
  }, [loadCore, user])

  async function signIn() {
    try {
      setErrorText('')
      const data = await api.login(loginForm)
      await setToken(data.token)
      setUser(data.user)
      setTab(data.user.role === 'driver' ? 'driverHome' : 'overview')
    } catch (err) {
      setErrorText(err.message)
    }
  }

  async function signOut() {
    await setToken('')
    setUser(null)
  }

  async function refresh() {
    setRefreshing(true)
    try {
      await loadCore()
    } catch (err) {
      setErrorText(err.message)
    } finally {
      setRefreshing(false)
    }
  }

  if (booting) {
    return (
      <SafeAreaView style={styles.center}>
        <ActivityIndicator color={colors.primary} size="large" />
        <Text style={styles.muted}>正在进入叉车调度平台</Text>
      </SafeAreaView>
    )
  }

  if (!user) {
    return (
      <SafeAreaView style={styles.login}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.loginCard}>
          <View style={styles.brand}>
            <Text style={styles.brandLogo}>FD</Text>
            <View>
              <Text style={styles.loginTitle}>叉车调度</Text>
              <Text style={styles.loginSub}>企业级移动运行台</Text>
            </View>
          </View>
          <Field label="账号" value={loginForm.username} onChangeText={(username) => setLoginForm({ ...loginForm, username })} />
          <Field label="密码" value={loginForm.password} secureTextEntry onChangeText={(password) => setLoginForm({ ...loginForm, password })} />
          {!!errorText && <Text style={styles.error}>{errorText}</Text>}
          <ActionButton label="登录" icon="login" onPress={signIn} />
          <Text style={styles.apiHint}>后端：{API_BASE}</Text>
        </KeyboardAvoidingView>
      </SafeAreaView>
    )
  }

  const tabs = isAdmin
    ? [
        ['overview', '总览', 'view-dashboard-outline'],
        ['tasks', '任务', 'clipboard-list-outline'],
        ['manage', '管理', 'tune-variant'],
        ['reports', '报表', 'chart-bar'],
        ['alerts', '异常', 'alert-outline'],
      ]
    : [
        ['driverHome', '主页', 'home-variant-outline'],
        ['driverTasks', '任务', 'clipboard-check-outline'],
        ['driverMap', '地图', 'map-marker-path'],
        ['driverMine', '我的', 'account-outline'],
      ]

  return (
    <SafeAreaView style={styles.shell}>
      <View style={styles.topBar}>
        <View>
          <Text style={styles.pageTitle}>{tabs.find((item) => item[0] === tab)?.[1] || '调度平台'}</Text>
          <Text style={styles.muted}>{user.name} · {user.role === 'admin' ? '管理员' : '司机'}</Text>
        </View>
        <Pressable style={styles.iconBtn} onPress={refresh}>
          <MaterialCommunityIcons name="refresh" color={colors.primary} size={22} />
        </Pressable>
      </View>
      {!!errorText && <Text style={styles.inlineError}>{errorText}</Text>}
      <ScrollView
        style={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}
        contentContainerStyle={styles.contentInner}
      >
        {tab === 'overview' && <OverviewScreen overview={overview} tasks={tasks} alerts={alerts} />}
        {tab === 'tasks' && <TaskScreen points={points} tasks={tasks} vehicles={vehicles} onChanged={loadCore} />}
        {tab === 'manage' && (
          <ManageScreen
            panel={adminPanel}
            setPanel={setAdminPanel}
            points={points}
            vehicles={vehicles}
            drivers={drivers}
            rules={rules}
            schedules={schedules}
            users={users}
            onChanged={loadCore}
          />
        )}
        {tab === 'reports' && (
          <ReportsScreen period={reportPeriod} setPeriod={setReportPeriod} report={driverReport} />
        )}
        {tab === 'alerts' && <AlertsScreen alerts={alerts} onChanged={loadCore} />}
        {tab === 'driverHome' && (
          <DriverHome user={user} report={myReport} vehicles={vehicles} onChanged={async () => {
            const currentUser = await api.get('/api/auth/me')
            setUser(currentUser)
            await loadCore()
          }} />
        )}
        {tab === 'driverTasks' && <DriverTasksScreen tasks={tasks} onChanged={loadCore} />}
        {tab === 'driverMap' && <MapCard vehicles={vehicles} points={points} tasks={tasks} />}
        {tab === 'driverMine' && <MineScreen user={user} report={myReport} signOut={signOut} />}
      </ScrollView>
      <View style={styles.tabBar}>
        {tabs.map(([key, label, icon]) => (
          <Pressable key={key} style={[styles.tabItem, tab === key && styles.tabItemActive]} onPress={() => setTab(key)}>
            <MaterialCommunityIcons name={icon} size={21} color={tab === key ? colors.primary : colors.muted} />
            <Text style={[styles.tabLabel, tab === key && styles.tabLabelActive]}>{label}</Text>
          </Pressable>
        ))}
      </View>
    </SafeAreaView>
  )
}

function OverviewScreen({ overview, tasks, alerts }) {
  const metrics = overview.metrics || {}
  const pending = tasks.filter((task) => ['pending_dispatch', 'assigned'].includes(task.status))
  return (
    <View>
      <View style={styles.statsGrid}>
        <StatCard label="今日任务" value={metrics.todayTasks ?? 0} sub={`完成率 ${metrics.completionRate ?? 0}%`} />
        <StatCard label="执行中" value={metrics.executingTasks ?? 0} sub="已派单/运输中" />
        <StatCard label="可用叉车" value={metrics.availableForklifts ?? 0} sub={`在线 ${metrics.onlineForklifts ?? 0} 台`} />
        <StatCard label="开放异常" value={metrics.openAlerts ?? 0} sub="需闭环处理" />
      </View>
      <MapCard vehicles={overview.vehicles || []} points={overview.mapPoints || []} tasks={pending} />
      <Card title="司机当天任务甘特图">
        <Gantt rows={overview.driverGantt || []} />
      </Card>
      <Card title="待处理任务">
        {pending.slice(0, 8).map((task) => <TaskRow key={task.id} task={task} compact />)}
      </Card>
      <Card title="异常预警">
        {(alerts.length ? alerts : overview.alerts || []).slice(0, 6).map((item) => (
          <View key={item.id} style={styles.listRow}>
            <Badge text={item.severity || 'info'} tone={item.severity === 'critical' ? 'danger' : 'warning'} />
            <View style={styles.flex}>
              <Text style={styles.rowTitle}>{item.title}</Text>
              <Text style={styles.rowSub}>{item.message}</Text>
            </View>
          </View>
        ))}
      </Card>
    </View>
  )
}

function TaskScreen({ points, tasks, vehicles, onChanged }) {
  const [form, setForm] = useState(emptyTaskForm)
  const [mode, setMode] = useState('select')
  const [mapPick, setMapPick] = useState('origin')
  const [draftPoints, setDraftPoints] = useState({ origin: null, dest: null })
  const [filter, setFilter] = useState('all')
  const filtered = tasks.filter((task) => filter === 'all' || task.status === filter)

  useEffect(() => {
    if (!form.originPointId && points[0]) setForm((old) => ({ ...old, originPointId: String(points[0].id) }))
    if (!form.destPointId && points[1]) setForm((old) => ({ ...old, destPointId: String(points[1].id) }))
  }, [form.destPointId, form.originPointId, points])

  async function ensureMapPoint(target) {
    const draft = draftPoints[target]
    if (!draft) return target === 'origin' ? form.originPointId : form.destPointId
    const created = await api.post('/api/map-points', {
      name: target === 'origin' ? '临时取货点' : '临时送货点',
      pointType: target === 'origin' ? 'pickup' : 'dropoff',
      area: '临时任务',
      x: draft.x,
      y: draft.y,
      geofenceRadius: 5,
      temporary: true,
    })
    return created.id
  }

  async function createTask() {
    const originPointId = await ensureMapPoint('origin')
    const destPointId = await ensureMapPoint('dest')
    await api.post('/api/tasks', { ...form, originPointId, destPointId })
    setDraftPoints({ origin: null, dest: null })
    await onChanged()
  }

  async function dispatch(task, forkliftId) {
    await api.post(`/api/tasks/${task.id}/assign`, forkliftId ? { forkliftId } : {})
    await onChanged()
  }

  async function complete(task) {
    await api.post(`/api/tasks/${task.id}/status`, { status: 'completed', message: '管理员移动端确认完成' })
    await onChanged()
  }

  return (
    <View>
      <Card title="发布搬运任务">
        <Segment value={mode} onChange={setMode} items={[['select', '下拉选择'], ['map', '地图标记']]} />
        {mode === 'select' ? (
          <View>
            <PickerLike label="取货地址" value={form.originPointId} options={makeOptions(points)} onChange={(originPointId) => setForm({ ...form, originPointId })} />
            <PickerLike label="送货地址" value={form.destPointId} options={makeOptions(points)} onChange={(destPointId) => setForm({ ...form, destPointId })} />
          </View>
        ) : (
          <View>
            <Segment value={mapPick} onChange={setMapPick} items={[['origin', '标取货点'], ['dest', '标送货点']]} />
            <MapCard points={points} vehicles={[]} tasks={[]} pickMode onPick={(point) => setDraftPoints({ ...draftPoints, [mapPick]: point })} extraMarkers={[
              draftPoints.origin && { ...draftPoints.origin, label: '取', tone: 'primary' },
              draftPoints.dest && { ...draftPoints.dest, label: '送', tone: 'warning' },
            ].filter(Boolean)} />
          </View>
        )}
        <Field label="货物类型" value={form.cargoType} onChangeText={(cargoType) => setForm({ ...form, cargoType })} />
        <View style={styles.twoCols}>
          <Field label="重量 kg" value={form.estimatedWeight} keyboardType="numeric" onChangeText={(estimatedWeight) => setForm({ ...form, estimatedWeight })} />
          <Field label="托盘/件数" value={form.palletCount} keyboardType="numeric" onChangeText={(palletCount) => setForm({ ...form, palletCount })} />
        </View>
        <PickerLike label="优先级" value={form.priority} options={['S', 'A', 'B', 'C'].map((v) => ({ label: v, value: v }))} onChange={(priority) => setForm({ ...form, priority })} />
        <Field label="备注" value={form.note} onChangeText={(note) => setForm({ ...form, note })} />
        <ActionButton label="提交任务" icon="send" onPress={createTask} />
      </Card>
      <Card title="任务池">
        <Segment value={filter} onChange={setFilter} items={[['all', '全部'], ['pending_dispatch', '待派'], ['assigned', '待接'], ['completed', '完成']]} />
        {filtered.map((task) => (
          <TaskRow key={task.id} task={task}>
            <View style={styles.rowActions}>
              <ActionChip label="自动派单" onPress={() => dispatch(task)} disabled={task.status !== 'pending_dispatch'} />
              {vehicles.filter((v) => v.status === 'idle' && v.online).slice(0, 2).map((vehicle) => (
                <ActionChip key={vehicle.id} label={vehicle.code} onPress={() => dispatch(task, vehicle.id)} disabled={task.status !== 'pending_dispatch'} />
              ))}
              <ActionChip label="完成" onPress={() => complete(task)} disabled={task.status === 'completed'} />
            </View>
          </TaskRow>
        ))}
      </Card>
    </View>
  )
}

function ManageScreen({ panel, setPanel, points, vehicles, drivers, rules, schedules, users, onChanged }) {
  return (
    <View>
      <Card>
        <Segment
          value={panel}
          onChange={setPanel}
          items={[
            ['points', '点位'],
            ['vehicles', '叉车'],
            ['rules', '规则'],
            ['schedule', '排班'],
            ['users', '账号'],
          ]}
        />
      </Card>
      {panel === 'points' && <PointManager points={points} onChanged={onChanged} />}
      {panel === 'vehicles' && <VehicleManager vehicles={vehicles} onChanged={onChanged} />}
      {panel === 'rules' && <RuleManager rules={rules} onChanged={onChanged} />}
      {panel === 'schedule' && <ScheduleManager drivers={drivers} vehicles={vehicles} schedules={schedules} onChanged={onChanged} />}
      {panel === 'users' && <UserManager users={users} onChanged={onChanged} />}
    </View>
  )
}

function PointManager({ points, onChanged }) {
  const [form, setForm] = useState(emptyPointForm)
  const [editingId, setEditingId] = useState(null)
  async function save() {
    if (editingId) await api.patch(`/api/map-points/${editingId}`, form)
    else await api.post('/api/map-points', form)
    setEditingId(null)
    setForm(emptyPointForm)
    await onChanged()
  }
  async function remove(row) {
    await api.del(`/api/map-points/${row.id}`)
    await onChanged()
  }
  return (
    <Card title={editingId ? '修改取送货点' : '新增取送货点'}>
      <MapCard points={points} vehicles={[]} tasks={[]} pickMode onPick={(point) => setForm({ ...form, x: String(point.x), y: String(point.y) })} />
      <Field label="名称" value={form.name} onChangeText={(name) => setForm({ ...form, name })} />
      <View style={styles.twoCols}>
        <PickerLike label="类型" value={form.pointType} options={[['pickup', '取货点'], ['dropoff', '送货点'], ['handover', '交接点']].map(([value, label]) => ({ value, label }))} onChange={(pointType) => setForm({ ...form, pointType })} />
        <Field label="区域" value={form.area} onChangeText={(area) => setForm({ ...form, area })} />
      </View>
      <View style={styles.twoCols}>
        <Field label="X" value={String(form.x)} keyboardType="numeric" onChangeText={(x) => setForm({ ...form, x })} />
        <Field label="Y" value={String(form.y)} keyboardType="numeric" onChangeText={(y) => setForm({ ...form, y })} />
      </View>
      <View style={styles.twoCols}>
        <Field label="纬度" value={String(form.lat)} keyboardType="numeric" onChangeText={(lat) => setForm({ ...form, lat })} />
        <Field label="经度" value={String(form.lng)} keyboardType="numeric" onChangeText={(lng) => setForm({ ...form, lng })} />
      </View>
      <ActionButton label={editingId ? '保存修改' : '保存点位'} icon="content-save" onPress={save} />
      <ListTitle title="点位列表" count={points.length} />
      {points.map((row) => (
        <View key={row.id} style={styles.listRow}>
          <View style={styles.flex}>
            <Text style={styles.rowTitle}>{row.name}</Text>
            <Text style={styles.rowSub}>{row.area} · X {row.x} / Y {row.y}</Text>
          </View>
          <ActionChip label="编辑" onPress={() => { setEditingId(row.id); setForm({ ...emptyPointForm, ...row, pointType: row.pointType || row.point_type || 'pickup', geofenceRadius: String(row.geofenceRadius || 5), x: String(row.x), y: String(row.y), lat: row.lat ? String(row.lat) : '', lng: row.lng ? String(row.lng) : '' }) }} />
          <ActionChip label="删除" tone="danger" onPress={() => remove(row)} />
        </View>
      ))}
    </Card>
  )
}

function VehicleManager({ vehicles, onChanged }) {
  const [form, setForm] = useState(emptyVehicleForm)
  const [editingId, setEditingId] = useState(null)
  async function save() {
    if (editingId) await api.patch(`/api/vehicles/${editingId}`, form)
    else await api.post('/api/vehicles', form)
    setEditingId(null)
    setForm(emptyVehicleForm)
    await onChanged()
  }
  async function remove(row) {
    await api.del(`/api/vehicles/${row.id}`)
    await onChanged()
  }
  return (
    <Card title={editingId ? '修改叉车' : '新增叉车'}>
      <Field label="车辆编号" value={form.code} onChangeText={(code) => setForm({ ...form, code })} />
      <View style={styles.twoCols}>
        <PickerLike label="动力" value={form.powerType} options={[['electric', '电动叉车'], ['diesel', '柴油叉车'], ['gasoline', '油叉车']].map(([value, label]) => ({ value, label }))} onChange={(powerType) => setForm({ ...form, powerType })} />
        <Field label="吨位" value={form.tonnage} keyboardType="numeric" onChangeText={(tonnage) => setForm({ ...form, tonnage })} />
      </View>
      <View style={styles.twoCols}>
        <Field label="电量%" value={form.batteryLevel} keyboardType="numeric" onChangeText={(batteryLevel) => setForm({ ...form, batteryLevel })} />
        <Field label="油量%" value={form.fuelLevel} keyboardType="numeric" onChangeText={(fuelLevel) => setForm({ ...form, fuelLevel })} />
      </View>
      <ActionButton label={editingId ? '保存修改' : '新增叉车'} icon="forklift" onPress={save} />
      <ListTitle title="叉车台账" count={vehicles.length} />
      {vehicles.map((row) => (
        <View key={row.id} style={styles.listRow}>
          <View style={styles.flex}>
            <Text style={styles.rowTitle}>{row.code}</Text>
            <Text style={styles.rowSub}>{row.powerType || row.power_type} · {row.tonnage}T · {statusLabel(row.status)}</Text>
          </View>
          <Badge text={`${row.batteryLevel ?? row.battery_level ?? row.fuelLevel ?? row.fuel_level ?? 0}%`} />
          <ActionChip label="编辑" onPress={() => { setEditingId(row.id); setForm({ ...emptyVehicleForm, ...row, code: row.code, powerType: row.powerType || row.power_type || 'electric', batteryLevel: String(row.batteryLevel ?? row.battery_level ?? 0), fuelLevel: String(row.fuelLevel ?? row.fuel_level ?? 0), tonnage: String(row.tonnage || 3) }) }} />
          <ActionChip label="删除" tone="danger" onPress={() => remove(row)} />
        </View>
      ))}
    </Card>
  )
}

function RuleManager({ rules, onChanged }) {
  const [form, setForm] = useState(emptyRuleForm)
  const [category, setCategory] = useState('all')
  const filtered = rules.filter((rule) => category === 'all' || rule.category === category)
  async function create() {
    await api.post('/api/rules', form)
    setForm(emptyRuleForm)
    await onChanged()
  }
  async function toggle(rule) {
    await api.patch(`/api/rules/${rule.id}`, { enabled: !rule.enabled })
    await onChanged()
  }
  async function remove(rule) {
    await api.del(`/api/rules/${rule.id}`)
    await onChanged()
  }
  return (
    <Card title="调度规则库">
      <Segment value={category} onChange={setCategory} items={[['all', '全部'], ['priority', '优先级'], ['filter', '过滤'], ['exception', '异常'], ['score', '评分']]} />
      <Field label="规则名称" value={form.name} onChangeText={(name) => setForm({ ...form, name })} />
      <View style={styles.twoCols}>
        <Field label="优先级" value={form.priority} keyboardType="numeric" onChangeText={(priority) => setForm({ ...form, priority })} />
        <Field label="权重" value={form.weight} keyboardType="numeric" onChangeText={(weight) => setForm({ ...form, weight })} />
      </View>
      <Field label="说明" value={form.description} onChangeText={(description) => setForm({ ...form, description })} />
      <ActionButton label="新增规则" icon="plus" onPress={create} />
      {filtered.map((rule) => (
        <View key={rule.id} style={styles.listRow}>
          <View style={styles.flex}>
            <Text style={styles.rowTitle}>{rule.name}</Text>
            <Text style={styles.rowSub}>{rule.category} · 权重 {rule.weight} · 优先级 {rule.priority}</Text>
          </View>
          <Badge text={rule.enabled ? '启用' : '停用'} tone={rule.enabled ? 'ok' : 'muted'} />
          <ActionChip label={rule.enabled ? '停用' : '启用'} onPress={() => toggle(rule)} />
          {rule.editable && <ActionChip label="删除" tone="danger" onPress={() => remove(rule)} />}
        </View>
      ))}
    </Card>
  )
}

function ScheduleManager({ drivers, vehicles, schedules, onChanged }) {
  const [form, setForm] = useState({ driverId: '', forkliftId: '', shiftCode: 'DAY', area: '全厂', status: 'scheduled' })
  useEffect(() => {
    if (!form.driverId && drivers[0]) setForm((old) => ({ ...old, driverId: String(drivers[0].id) }))
    if (!form.forkliftId && vehicles[0]) setForm((old) => ({ ...old, forkliftId: String(vehicles[0].id) }))
  }, [drivers, form.driverId, form.forkliftId, vehicles])
  async function createAssignment() {
    await api.post('/api/schedules/assignments', form)
    await onChanged()
  }
  async function bindVehicle() {
    await api.post('/api/bindings', { driverId: form.driverId, forkliftId: form.forkliftId, shiftCode: form.shiftCode })
    await onChanged()
  }
  async function closeBinding(row) {
    await api.post(`/api/bindings/${row.id}/close`, {})
    await onChanged()
  }
  return (
    <Card title="排班与绑定">
      <PickerLike label="司机" value={form.driverId} options={drivers.map((d) => ({ label: d.name || d.employeeNo || d.employee_no, value: String(d.id) }))} onChange={(driverId) => setForm({ ...form, driverId })} />
      <PickerLike label="叉车" value={form.forkliftId} options={vehicles.map((v) => ({ label: v.code, value: String(v.id) }))} onChange={(forkliftId) => setForm({ ...form, forkliftId })} />
      <View style={styles.rowActions}>
        <ActionButton label="新增排班" icon="calendar-plus" onPress={createAssignment} compact />
        <ActionButton label="立即绑定" icon="link-variant" onPress={bindVehicle} compact />
      </View>
      <ListTitle title="当前绑定" count={schedules.bindings?.length || 0} />
      {(schedules.bindings || []).slice(0, 30).map((row) => (
        <View key={row.id} style={styles.listRow}>
          <View style={styles.flex}>
            <Text style={styles.rowTitle}>{row.driverName || row.driver?.name || '司机'} / {row.forkliftCode || row.forklift?.code || '叉车'}</Text>
            <Text style={styles.rowSub}>{row.shiftCode || row.shift_code} · {statusLabel(row.status)}</Text>
          </View>
          {row.status === 'active' && <ActionChip label="解绑" onPress={() => closeBinding(row)} />}
        </View>
      ))}
    </Card>
  )
}

function UserManager({ users, onChanged }) {
  const [form, setForm] = useState(emptyUserForm)
  const [editingId, setEditingId] = useState(null)
  async function save() {
    if (editingId) await api.patch(`/api/users/${editingId}`, form)
    else await api.post('/api/users', form)
    setEditingId(null)
    setForm(emptyUserForm)
    await onChanged()
  }
  async function remove(row) {
    await api.del(`/api/users/${row.id}`)
    await onChanged()
  }
  return (
    <Card title={editingId ? '修改系统用户' : '新增系统用户'}>
      <View style={styles.twoCols}>
        <Field label="账号" value={form.username} onChangeText={(username) => setForm({ ...form, username })} />
        <Field label="姓名" value={form.name} onChangeText={(name) => setForm({ ...form, name })} />
      </View>
      <PickerLike label="角色" value={form.role} options={[{ label: '管理员', value: 'admin' }, { label: '叉车司机', value: 'driver' }]} onChange={(role) => setForm({ ...form, role })} />
      <View style={styles.twoCols}>
        <Field label="工号" value={form.employeeNo} onChangeText={(employeeNo) => setForm({ ...form, employeeNo })} />
        <Field label="企业微信UserID" value={form.wecomUserId} onChangeText={(wecomUserId) => setForm({ ...form, wecomUserId })} />
      </View>
      <ActionButton label={editingId ? '保存修改' : '新增用户'} icon="account-plus" onPress={save} />
      <ListTitle title="账号列表" count={users.length} />
      {users.map((row) => (
        <View key={row.id} style={styles.listRow}>
          <View style={styles.flex}>
            <Text style={styles.rowTitle}>{row.name}</Text>
            <Text style={styles.rowSub}>{row.username} · {row.role} · {row.team || row.department}</Text>
          </View>
          <ActionChip label="编辑" onPress={() => { setEditingId(row.id); setForm({ ...emptyUserForm, ...row, employeeNo: row.driver?.employeeNo || row.driver?.employee_no || '' }) }} />
          <ActionChip label="删除" tone="danger" onPress={() => remove(row)} />
        </View>
      ))}
    </Card>
  )
}

function ReportsScreen({ period, setPeriod, report }) {
  const rows = report.rows || report.drivers || []
  async function exportCsv() {
    const header = ['司机', '班组', '完成任务', '总公里数', '作业时长', '单均公里']
    const body = rows.map((row) => [row.driverName || row.name, row.team, row.completedTasks, row.totalDistance, row.workingMinutes, row.avgDistance])
    const csv = [header, ...body].map((line) => line.map((cell) => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(',')).join('\n')
    const uri = `${FileSystem.cacheDirectory}driver-report-${period}.csv`
    await FileSystem.writeAsStringAsync(uri, csv, { encoding: FileSystem.EncodingType.UTF8 })
    if (await Sharing.isAvailableAsync()) {
      await Sharing.shareAsync(uri)
    } else {
      Alert.alert('已导出', uri)
    }
  }
  return (
    <View>
      <Card title="司机工作报表">
        <Segment value={period} onChange={setPeriod} items={[['day', '日'], ['week', '周'], ['month', '月'], ['quarter', '季'], ['year', '年']]} />
        <BarChart rows={rows} valueKey="completedTasks" labelKey="driverName" />
        <ActionButton label="导出 CSV" icon="download" onPress={exportCsv} />
      </Card>
      <Card title="明细">
        {rows.map((row, index) => (
          <View key={`${row.driverId || index}`} style={styles.listRow}>
            <View style={styles.flex}>
              <Text style={styles.rowTitle}>{row.driverName || row.name}</Text>
              <Text style={styles.rowSub}>{row.team || '-'} · {row.workingMinutes || 0} 分钟</Text>
            </View>
            <Badge text={`${row.completedTasks || 0} 单`} />
            <Badge text={`${row.totalDistance || 0} km`} />
          </View>
        ))}
      </Card>
    </View>
  )
}

function AlertsScreen({ alerts, onChanged }) {
  const [severity, setSeverity] = useState('all')
  const [selected, setSelected] = useState({})
  const filtered = alerts.filter((item) => severity === 'all' || item.severity === severity)
  async function closeOne(alert) {
    await api.post(`/api/alerts/${alert.id}/close`, { message: '移动端已确认闭环' })
    await onChanged()
  }
  async function closeBatch() {
    const ids = Object.entries(selected).filter(([, checked]) => checked).map(([id]) => Number(id))
    if (!ids.length) return
    await api.post('/api/alerts/batch-close', { ids, message: '移动端批量闭环' })
    setSelected({})
    await onChanged()
  }
  return (
    <Card title="异常闭环中心">
      <Segment value={severity} onChange={setSeverity} items={[['all', '全部'], ['critical', '严重'], ['warning', '预警'], ['info', '信息']]} />
      <ActionButton label="批量关闭已选" icon="check-all" onPress={closeBatch} />
      {filtered.map((item) => (
        <Pressable key={item.id} style={[styles.alertCard, selected[item.id] && styles.alertSelected]} onPress={() => setSelected({ ...selected, [item.id]: !selected[item.id] })}>
          <View style={styles.rowActions}>
            <Badge text={item.severity} tone={item.severity === 'critical' ? 'danger' : 'warning'} />
            <ActionChip label="关闭" onPress={() => closeOne(item)} />
          </View>
          <Text style={styles.rowTitle}>{item.title}</Text>
          <Text style={styles.rowSub}>{item.message}</Text>
          <Text style={styles.tiny}>{item.suggestion}</Text>
        </Pressable>
      ))}
    </Card>
  )
}

function DriverHome({ user, report, vehicles, onChanged }) {
  const rows = report.rows || report.drivers || []
  const mine = rows[0] || {}
  async function toggleOnline() {
    const current = user.driver?.shiftStatus || user.driver?.shift_status
    await api.patch('/api/driver/status', { shiftStatus: current === 'on_shift' ? 'off_shift' : 'on_shift' })
    await onChanged()
  }
  async function requestForklift(vehicle) {
    await api.post('/api/driver/forklift-requests', { forkliftId: vehicle.id })
    await onChanged()
  }
  return (
    <View>
      <Card title="我的工作台">
        <View style={styles.statsGrid}>
          <StatCard label="完成任务" value={mine.completedTasks || 0} sub="当前周期" />
          <StatCard label="总公里数" value={`${mine.totalDistance || 0}`} sub="km" />
          <StatCard label="作业时长" value={`${mine.workingMinutes || 0}`} sub="分钟" />
          <StatCard label="状态" value={(user.driver?.shiftStatus || user.driver?.shift_status) === 'on_shift' ? '在线' : '离线'} sub={user.driver?.bindStatus || user.driver?.bind_status || '未绑定'} />
        </View>
        <ActionButton label="切换上下线" icon="power" onPress={toggleOnline} />
        <BarChart rows={rows} valueKey="completedTasks" labelKey="driverName" />
      </Card>
      <Card title="可申请空闲叉车">
        <MapCard vehicles={vehicles.filter((vehicle) => vehicle.status === 'idle' && vehicle.online)} points={[]} tasks={[]} />
        {vehicles.filter((vehicle) => vehicle.status === 'idle' && vehicle.online).map((vehicle) => (
          <View key={vehicle.id} style={styles.listRow}>
            <View style={styles.flex}>
              <Text style={styles.rowTitle}>{vehicle.code}</Text>
              <Text style={styles.rowSub}>{vehicle.currentArea || vehicle.current_area} · X {vehicle.currentX || vehicle.current_x}</Text>
            </View>
            <ActionChip label="申请" onPress={() => requestForklift(vehicle)} />
          </View>
        ))}
      </Card>
    </View>
  )
}

function DriverTasksScreen({ tasks, onChanged }) {
  const [reasons, setReasons] = useState({})
  async function accept(task) {
    await api.post(`/api/tasks/${task.id}/driver-accept`, {})
    await onChanged()
  }
  async function reject(task) {
    const reason = reasons[task.id]
    if (!reason) {
      Alert.alert('需要填写拒绝原因')
      return
    }
    await api.post(`/api/tasks/${task.id}/driver-reject`, { reason })
    await onChanged()
  }
  async function complete(task) {
    await api.post(`/api/tasks/${task.id}/driver-complete`, {})
    await onChanged()
  }
  return (
    <Card title="我的任务">
      {tasks.map((task) => (
        <TaskRow key={task.id} task={task}>
          {task.status === 'assigned' && (
            <View>
              <Field label="拒绝原因" value={reasons[task.id] || ''} onChangeText={(value) => setReasons({ ...reasons, [task.id]: value })} />
              <View style={styles.rowActions}>
                <ActionChip label="接受" onPress={() => accept(task)} />
                <ActionChip label="拒绝" tone="danger" onPress={() => reject(task)} />
              </View>
            </View>
          )}
          {task.status !== 'completed' && task.status !== 'assigned' && <ActionButton label="确认完成" icon="check" onPress={() => complete(task)} />}
        </TaskRow>
      ))}
    </Card>
  )
}

function MineScreen({ user, report, signOut }) {
  const mine = (report.rows || report.drivers || [])[0] || {}
  return (
    <View>
      <Card title="个人信息">
        <Text style={styles.rowTitle}>{user.name}</Text>
        <Text style={styles.rowSub}>{user.username} · {user.team || user.department}</Text>
        <Text style={styles.rowSub}>企业微信：{user.wecomUserId || user.wecom_user_id || '-'}</Text>
      </Card>
      <Card title="工作统计">
        <BarChart rows={[mine]} valueKey="completedTasks" labelKey="driverName" />
      </Card>
      <ActionButton label="退出登录" icon="logout" tone="danger" onPress={signOut} />
    </View>
  )
}

function MapCard({ vehicles = [], points = [], tasks = [], pickMode = false, onPick, extraMarkers = [] }) {
  const [size, setSize] = useState({ width: 1, height: 1 })
  const taskPoints = tasks.flatMap((task) => [
    task.origin && { ...task.origin, label: '取', tone: 'primary' },
    task.destination && { ...task.destination, label: '送', tone: 'warning' },
  ]).filter(Boolean)
  const markers = [
    ...points.map((point) => ({ x: point.x, y: point.y, label: point.pointType === 'dropoff' || point.point_type === 'dropoff' ? '送' : '取', tone: 'point' })),
    ...vehicles.map((vehicle) => ({ x: vehicle.currentX ?? vehicle.current_x, y: vehicle.currentY ?? vehicle.current_y, label: vehicle.code?.replace('FLC-', '') || '车', tone: 'vehicle' })),
    ...taskPoints,
    ...extraMarkers,
  ].filter((item) => item.x !== undefined && item.y !== undefined)

  return (
    <Card title="厂区地图">
      <Pressable
        style={styles.mapWrap}
        onLayout={(event) => setSize(event.nativeEvent.layout)}
        onPress={(event) => {
          if (!pickMode || !onPick) return
          const { locationX, locationY } = event.nativeEvent
          onPick({ x: +(locationX / size.width * 100).toFixed(2), y: +(locationY / size.height * 100).toFixed(2) })
        }}
      >
        <ImageBackground source={{ uri: `${API_BASE}/api/basemap/image` }} style={styles.mapImage} resizeMode="cover">
          {markers.map((marker, index) => (
            <View
              key={`${marker.label}-${index}`}
              style={[
                styles.marker,
                {
                  left: `${Number(marker.x)}%`,
                  top: `${Number(marker.y)}%`,
                  backgroundColor: marker.tone === 'warning' ? colors.warning : marker.tone === 'vehicle' ? colors.primary : colors.blue,
                },
              ]}
            >
              <Text style={styles.markerText}>{marker.label}</Text>
            </View>
          ))}
        </ImageBackground>
      </Pressable>
      {pickMode && <Text style={styles.tiny}>点击地图即可取 X/Y 坐标，保存后由后端统一换算/定位。</Text>}
    </Card>
  )
}

function TaskRow({ task, children, compact }) {
  return (
    <View style={styles.taskCard}>
      <View style={styles.rowActions}>
        <Badge text={task.priority || 'B'} tone="custom" color={priorityColor(task.priority)} />
        <Badge text={statusLabel(task.status)} />
      </View>
      <Text style={styles.rowTitle}>{task.taskNo || task.task_no}</Text>
      <Text style={styles.rowSub}>{task.originLabel || task.origin_label} → {task.destLabel || task.dest_label}</Text>
      <Text style={styles.rowSub}>{task.cargoType || task.cargo_type} / {task.estimatedWeight || task.estimated_weight}kg</Text>
      {!compact && <Text style={styles.tiny}>派单：{task.assignedForkliftCode || task.assigned_forklift_code || '-'} / {task.assignedDriverName || task.assigned_driver_name || '-'}</Text>}
      {children}
    </View>
  )
}

function Gantt({ rows }) {
  if (!rows.length) return <Text style={styles.muted}>今天暂无司机任务分布</Text>
  return rows.map((row, index) => (
    <View key={row.driverId || index} style={styles.ganttRow}>
      <Text style={styles.ganttName}>{row.driverName || row.name}</Text>
      <View style={styles.ganttTrack}>
        {(row.segments || []).map((seg, i) => (
          <View
            key={i}
            style={[
              styles.ganttSeg,
              {
                left: `${Math.max(0, Math.min(100, seg.left || seg.startPercent || 0))}%`,
                width: `${Math.max(2, Math.min(100, seg.width || seg.durationPercent || 5))}%`,
              },
            ]}
          />
        ))}
      </View>
    </View>
  ))
}

function BarChart({ rows, valueKey, labelKey }) {
  const max = Math.max(1, ...rows.map((row) => Number(row[valueKey] || 0)))
  if (!rows.length) return <Text style={styles.muted}>暂无报表数据</Text>
  return (
    <View style={styles.chart}>
      {rows.slice(0, 8).map((row, index) => {
        const value = Number(row[valueKey] || 0)
        return (
          <View key={row.driverId || index} style={styles.barRow}>
            <Text style={styles.barName}>{row[labelKey] || row.name || '司机'}</Text>
            <View style={styles.barTrack}>
              <View style={[styles.barFill, { width: `${(value / max) * 100}%` }]} />
            </View>
            <Text style={styles.barValue}>{value}</Text>
          </View>
        )
      })}
    </View>
  )
}

function Card({ title, children }) {
  return (
    <View style={styles.card}>
      {!!title && <Text style={styles.cardTitle}>{title}</Text>}
      {children}
    </View>
  )
}

function StatCard({ label, value, sub }) {
  return (
    <View style={styles.statCard}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statSub}>{sub}</Text>
    </View>
  )
}

function Field({ label, style, ...props }) {
  return (
    <View style={[styles.field, style]}>
      <Text style={styles.label}>{label}</Text>
      <TextInput placeholderTextColor="#91a39e" style={styles.input} {...props} />
    </View>
  )
}

function PickerLike({ label, value, options, onChange }) {
  const [open, setOpen] = useState(false)
  const current = options.find((item) => item.value === String(value))
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <Pressable style={styles.select} onPress={() => setOpen(true)}>
        <Text style={styles.selectText}>{current?.label || '请选择'}</Text>
        <MaterialCommunityIcons name="chevron-down" size={20} color={colors.muted} />
      </Pressable>
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.modalMask} onPress={() => setOpen(false)}>
          <View style={styles.modalSheet}>
            {options.map((item) => (
              <Pressable key={item.value} style={styles.option} onPress={() => { onChange(item.value); setOpen(false) }}>
                <Text style={styles.optionText}>{item.label}</Text>
              </Pressable>
            ))}
          </View>
        </Pressable>
      </Modal>
    </View>
  )
}

function Segment({ value, onChange, items }) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.segment}>
      {items.map(([key, label]) => (
        <Pressable key={key} style={[styles.segmentItem, value === key && styles.segmentActive]} onPress={() => onChange(key)}>
          <Text style={[styles.segmentText, value === key && styles.segmentTextActive]}>{label}</Text>
        </Pressable>
      ))}
    </ScrollView>
  )
}

function ActionButton({ label, icon, onPress, tone, compact }) {
  return (
    <Pressable style={[styles.actionBtn, compact && styles.actionBtnCompact, tone === 'danger' && styles.actionDanger]} onPress={onPress}>
      {!!icon && <MaterialCommunityIcons name={icon} color="#fff" size={18} />}
      <Text style={styles.actionText}>{label}</Text>
    </Pressable>
  )
}

function ActionChip({ label, onPress, tone, disabled }) {
  return (
    <Pressable style={[styles.chip, tone === 'danger' && styles.chipDanger, disabled && styles.disabled]} onPress={disabled ? undefined : onPress}>
      <Text style={[styles.chipText, tone === 'danger' && styles.chipDangerText]}>{label}</Text>
    </Pressable>
  )
}

function Badge({ text, tone, color }) {
  return (
    <View style={[styles.badge, tone === 'danger' && styles.badgeDanger, tone === 'warning' && styles.badgeWarning, tone === 'muted' && styles.badgeMuted, color && { backgroundColor: color }]}>
      <Text style={[styles.badgeText, color && { color: '#fff' }]}>{text}</Text>
    </View>
  )
}

function ListTitle({ title, count }) {
  return (
    <View style={styles.listTitle}>
      <Text style={styles.cardTitle}>{title}</Text>
      <Text style={styles.muted}>{count} 条</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  shell: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg, gap: 12 },
  login: { flex: 1, backgroundColor: colors.primaryDark, justifyContent: 'center', padding: 20 },
  loginCard: { backgroundColor: colors.card, borderRadius: 18, padding: 20, ...shadow },
  brand: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 24 },
  brandLogo: { width: 50, height: 50, borderRadius: 14, backgroundColor: colors.primary, color: '#fff', textAlign: 'center', textAlignVertical: 'center', fontWeight: '800', fontSize: 20 },
  loginTitle: { fontSize: 24, fontWeight: '800', color: colors.ink },
  loginSub: { color: colors.muted, marginTop: 4 },
  apiHint: { marginTop: 14, color: colors.muted, fontSize: 12 },
  topBar: { paddingHorizontal: 18, paddingTop: 8, paddingBottom: 12, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: colors.bg },
  pageTitle: { color: colors.ink, fontSize: 26, fontWeight: '900' },
  iconBtn: { width: 42, height: 42, borderRadius: 12, backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center', ...shadow },
  content: { flex: 1 },
  contentInner: { paddingHorizontal: 14, paddingBottom: 110 },
  tabBar: { position: 'absolute', left: 12, right: 12, bottom: 12, flexDirection: 'row', backgroundColor: colors.card, borderRadius: 18, padding: 8, ...shadow },
  tabItem: { flex: 1, alignItems: 'center', paddingVertical: 8, borderRadius: 12, gap: 2 },
  tabItemActive: { backgroundColor: colors.soft },
  tabLabel: { fontSize: 12, color: colors.muted },
  tabLabelActive: { color: colors.primary, fontWeight: '700' },
  inlineError: { marginHorizontal: 16, marginBottom: 8, color: colors.danger },
  error: { color: colors.danger, marginBottom: 10 },
  muted: { color: colors.muted },
  tiny: { color: colors.muted, fontSize: 12, lineHeight: 18, marginTop: 6 },
  card: { backgroundColor: colors.card, borderRadius: 16, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: colors.line, ...shadow },
  cardTitle: { fontSize: 18, fontWeight: '800', color: colors.ink, marginBottom: 10 },
  statsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  statCard: { width: '48%', backgroundColor: colors.card, borderRadius: 16, padding: 14, borderWidth: 1, borderColor: colors.line, marginBottom: 10 },
  statLabel: { color: colors.muted, fontSize: 13 },
  statValue: { fontSize: 27, fontWeight: '900', color: colors.ink, marginTop: 8 },
  statSub: { color: colors.muted, marginTop: 6, fontSize: 12 },
  field: { flex: 1, marginBottom: 10 },
  label: { fontSize: 13, color: colors.ink, marginBottom: 6, fontWeight: '600' },
  input: { minHeight: 46, borderRadius: 10, borderWidth: 1, borderColor: colors.line, paddingHorizontal: 12, color: colors.ink, backgroundColor: '#fbfdfc' },
  select: { minHeight: 46, borderRadius: 10, borderWidth: 1, borderColor: colors.line, paddingHorizontal: 12, backgroundColor: '#fbfdfc', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  selectText: { color: colors.ink },
  twoCols: { flexDirection: 'row', gap: 10 },
  actionBtn: { minHeight: 46, borderRadius: 10, backgroundColor: colors.primary, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 4, marginBottom: 10, paddingHorizontal: 12 },
  actionBtnCompact: { flex: 1 },
  actionDanger: { backgroundColor: colors.danger },
  actionText: { color: '#fff', fontWeight: '800' },
  rowActions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, alignItems: 'center', marginBottom: 8 },
  chip: { backgroundColor: colors.soft, paddingHorizontal: 10, paddingVertical: 8, borderRadius: 9 },
  chipText: { color: colors.primary, fontWeight: '700', fontSize: 12 },
  chipDanger: { backgroundColor: '#f7e3e3' },
  chipDangerText: { color: colors.danger },
  disabled: { opacity: 0.35 },
  badge: { alignSelf: 'flex-start', paddingHorizontal: 9, paddingVertical: 5, borderRadius: 8, backgroundColor: colors.soft },
  badgeText: { color: colors.primary, fontWeight: '800', fontSize: 12 },
  badgeDanger: { backgroundColor: '#f7e3e3' },
  badgeWarning: { backgroundColor: '#fff0cf' },
  badgeMuted: { backgroundColor: '#edf1ef' },
  listRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 11, borderBottomWidth: 1, borderBottomColor: colors.line },
  listTitle: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 8 },
  flex: { flex: 1 },
  rowTitle: { color: colors.ink, fontWeight: '800', fontSize: 15, lineHeight: 21 },
  rowSub: { color: colors.ink, lineHeight: 20, marginTop: 2 },
  taskCard: { borderWidth: 1, borderColor: colors.line, borderRadius: 14, padding: 12, marginBottom: 10, backgroundColor: '#fbfdfc' },
  mapWrap: { height: 260, borderRadius: 14, overflow: 'hidden', backgroundColor: '#dfe8e5' },
  mapImage: { flex: 1 },
  marker: { position: 'absolute', width: 34, height: 26, marginLeft: -17, marginTop: -13, borderRadius: 9, alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: '#fff' },
  markerText: { color: '#fff', fontWeight: '900', fontSize: 11 },
  segment: { marginBottom: 12 },
  segmentItem: { paddingHorizontal: 12, paddingVertical: 8, backgroundColor: colors.soft, borderRadius: 10, marginRight: 8 },
  segmentActive: { backgroundColor: colors.primary },
  segmentText: { color: colors.primary, fontWeight: '700' },
  segmentTextActive: { color: '#fff' },
  modalMask: { flex: 1, backgroundColor: 'rgba(0,0,0,.25)', justifyContent: 'flex-end' },
  modalSheet: { backgroundColor: colors.card, borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 14, maxHeight: '60%' },
  option: { paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: colors.line },
  optionText: { color: colors.ink, fontSize: 16 },
  chart: { gap: 10, marginVertical: 8 },
  barRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  barName: { width: 82, color: colors.ink, fontWeight: '700' },
  barTrack: { flex: 1, height: 10, borderRadius: 999, backgroundColor: colors.soft, overflow: 'hidden' },
  barFill: { height: '100%', backgroundColor: colors.primary, borderRadius: 999 },
  barValue: { width: 36, textAlign: 'right', color: colors.ink, fontWeight: '800' },
  ganttRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  ganttName: { width: 76, color: colors.ink, fontWeight: '700' },
  ganttTrack: { flex: 1, height: 16, borderRadius: 999, backgroundColor: colors.soft, position: 'relative', overflow: 'hidden' },
  ganttSeg: { position: 'absolute', top: 0, bottom: 0, borderRadius: 999, backgroundColor: colors.primary },
  alertCard: { borderWidth: 1, borderColor: colors.line, borderRadius: 14, padding: 12, marginBottom: 10 },
  alertSelected: { borderColor: colors.primary, backgroundColor: colors.soft },
})
