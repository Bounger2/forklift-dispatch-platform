const { chromium } = require('playwright')

async function main() {
  const executablePath =
    process.env.PLAYWRIGHT_EXECUTABLE_PATH ||
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
  const browser = await chromium.launch({ headless: true, executablePath })
  const logs = []

  async function loginAs(username) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 980 } })
    page.on('console', (msg) => logs.push(`${username}:${msg.type()}: ${msg.text()}`))
    page.on('pageerror', (err) => logs.push(`${username}:pageerror: ${err.message}`))
    await page.goto('http://127.0.0.1:5173', { waitUntil: 'networkidle' })
    await page.fill('input[autocomplete="username"]', username)
    await page.fill('input[autocomplete="current-password"]', '123456')
    await page.click('button.primary-btn')
    await page.waitForSelector('.topbar h2', { timeout: 10000 })
    return page
  }

  const adminPage = await loginAs('admin')
  await adminPage.waitForSelector('text=厂区实时总览', { timeout: 10000 })
  const overview = await adminPage.evaluate(() => ({
    title: document.querySelector('.topbar h2')?.textContent || '',
    firstNav: document.querySelector('.nav-btn')?.textContent?.trim() || '',
    mapVisible: document.body.innerText.includes('厂区实时总览'),
  }))
  await adminPage.getByRole('button', { name: '调度任务' }).click()
  await adminPage.waitForSelector('text=发布搬运任务', { timeout: 10000 })
  const tasks = await adminPage.evaluate(() => ({
    taskPanel: document.body.innerText.includes('发布搬运任务'),
    auto: document.body.innerText.includes('自动派单'),
    manual: document.body.innerText.includes('手动派单'),
  }))
  await adminPage.getByRole('button', { name: '取送货点' }).click()
  await adminPage.waitForSelector('text=取送货点管理', { timeout: 10000 })
  const addresses = await adminPage.evaluate(() => ({
    form: document.body.innerText.includes('新增取送货点'),
    table: document.body.innerText.includes('地址清单'),
    basemap: document.body.innerText.includes('卫星底图'),
    scale: document.body.innerText.includes('50m'),
  }))
  await adminPage.getByRole('button', { name: '叉车管理' }).click()
  await adminPage.waitForSelector('text=叉车台账', { timeout: 10000 })
  const vehicles = await adminPage.evaluate(() => ({
    form: document.body.innerText.includes('新增叉车'),
    table: document.body.innerText.includes('叉车台账'),
    diesel: document.body.innerText.includes('柴油叉车'),
    deleteButton: document.body.innerText.includes('停用'),
  }))
  await adminPage.getByRole('button', { name: '调度规则' }).click()
  await adminPage.waitForSelector('text=调度规则库', { timeout: 10000 })
  const rules = await adminPage.evaluate(() => ({
    library: document.body.innerText.includes('调度规则库'),
    sliders: document.querySelectorAll('.rule-slider').length,
  }))
  await adminPage.getByRole('button', { name: '排班绑定' }).click()
  await adminPage.waitForSelector('text=新增排班', { timeout: 10000 })
  const schedules = await adminPage.evaluate(() => ({
    addForm: document.body.innerText.includes('新增排班'),
    bindForm: document.body.innerText.includes('司机车辆绑定修改'),
    deleteButton: document.body.innerText.includes('删除'),
  }))
  await adminPage.getByRole('button', { name: '账号管理' }).click()
  await adminPage.waitForSelector('text=新增系统用户', { timeout: 10000 })
  const admin = await adminPage.evaluate(() => ({
    title: document.querySelector('.topbar h2')?.textContent || '',
    usersPanel: document.body.innerText.includes('新增系统用户'),
    editButton: document.body.innerText.includes('修改'),
    reportsNav: document.body.innerText.includes('司机报表'),
    hasDispatcherRole: document.body.innerText.includes('调度员'),
  }))
  await adminPage.screenshot({ path: 'dispatch-overview.png', fullPage: true })
  await adminPage.close()

  const driverPage = await loginAs('d001')
  await driverPage.waitForSelector('text=我的运输任务', { timeout: 10000 })
  const driver = await driverPage.evaluate(() => ({
    title: document.querySelector('.topbar h2')?.textContent || '',
    myTasks: document.body.innerText.includes('我的运输任务'),
    hasDispatcherTaskPool: document.body.innerText.includes('调度任务'),
    assignedCards: document.querySelectorAll('.driver-task-card').length,
  }))
  await driverPage.close()

  const result = { overview, tasks, addresses, vehicles, rules, schedules, admin, driver }
  await browser.close()
  console.log(JSON.stringify({ result, logs }, null, 2))
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
