<template>
  <div class="factory-map" :class="`factory-map--${baseMode}`" ref="mapEl" @click="handleMapClick">
    <div v-if="baseMode === 'satellite'" class="factory-map__tile-layer" aria-hidden="true">
      <img
        v-for="tile in satelliteTiles"
        :key="tile.key"
        :src="tile.url"
        :style="{ left: `${tile.left}px`, top: `${tile.top}px` }"
        draggable="false"
        referrerpolicy="no-referrer"
      />
    </div>

    <svg v-else class="factory-map__base" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <rect width="100" height="100" fill="#dfe6e1" />
      <rect x="0" y="0" width="100" height="100" fill="#d9e2de" />
      <path d="M0 8 H100 M0 88 H100 M8 0 V100 M61 0 V100 M89 0 V100" stroke="#c7d0ca" stroke-width="1.2" fill="none" />
      <path d="M0 39 H100 M0 84 H100" stroke="#f4f1e9" stroke-width="3.8" fill="none" />
      <path d="M25 0 V100 M58 37 V88 M63 0 V100 M89 0 V72" stroke="#f4f1e9" stroke-width="2.8" fill="none" />
      <path d="M0 39 H100 M0 84 H100 M25 0 V100 M58 37 V88 M63 0 V100" stroke="#9fa8a2" stroke-width="0.55" fill="none" opacity="0.75" />

      <path d="M11 9 H60 V37 H11 Z" fill="#cfd9dc" stroke="#ffffff" stroke-width="0.8" />
      <path d="M11 44 H59 V83 H11 Z" fill="#cfd9dc" stroke="#ffffff" stroke-width="0.8" />
      <path d="M68 13 H86 V83 H68 Z" fill="#d5dcda" stroke="#ffffff" stroke-width="0.8" />
      <path d="M88 43 H99 V71 H88 Z" fill="#d6dfd8" stroke="#ffffff" stroke-width="0.7" opacity="0.85" />

      <path d="M14 12 H25 V24 H14 Z M28 12 H36 V37 H28 Z M38 11 H58 V34 H38 Z" fill="#9fb9dd" opacity="0.95" />
      <path d="M13 27 H31 V37 H13 Z M33 27 H57 V36 H33 Z" fill="#a8bfdc" opacity="0.9" />
      <path d="M13 47 H57 V61 H13 Z M13 66 H56 V80 H13 Z" fill="#93afd7" opacity="0.92" />
      <path d="M69 18 H84 V38 H69 Z M69 42 H84 V82 H69 Z" fill="#dfe4df" opacity="0.98" />
      <path d="M71 20 H82 M71 24 H82 M71 28 H82 M71 32 H82 M71 46 H82 M71 51 H82 M71 56 H82 M71 61 H82 M71 66 H82 M71 71 H82 M71 76 H82" stroke="#b6c0bc" stroke-width="0.55" />

      <path d="M14 26 H24 M14 30 H24 M14 34 H24 M35 17 H57 M35 21 H57 M35 25 H57 M14 51 H57 M14 56 H57 M14 70 H56 M14 75 H56" stroke="#eaf0f2" stroke-width="0.65" opacity="0.95" />
      <path d="M39 39 H59 M12 84 H61 M64 39 H100" stroke="#f8fafc" stroke-width="1.2" fill="none" opacity="0.8" />

      <path d="M2 0 V100 M98 0 V100" stroke="#aab6af" stroke-width="0.5" fill="none" opacity="0.5" />
      <path d="M5 11 H92 V87 H5 Z" fill="none" stroke="#5b8ff9" stroke-width="0.45" stroke-dasharray="1.4 1.1" opacity="0.9" />

    </svg>

    <template v-if="showLabels">
      <div class="factory-label label-west">西厂区</div>
      <div class="factory-label label-east">东厂区</div>
      <div class="factory-label label-road-top">同仁路</div>
      <div class="factory-label label-road-mid">乔九路</div>
      <div class="factory-label label-canal">通启运河</div>
    </template>

    <button
      v-for="point in points"
      :key="point.id"
      class="point-marker"
      :class="[`point-marker--${point.pointType}`, { 'point-marker--active': point.active }]"
      :style="markerStyle(point)"
      :title="`${point.name} | ${point.area}`"
      @click.stop="$emit('select-point', point)"
    >
      <span>{{ pointSymbol(point.pointType) }}</span>
    </button>

    <button
      v-for="vehicle in vehicles"
      :key="vehicle.id"
      class="vehicle-marker"
      :class="[`vehicle-marker--${vehicle.status}`, { 'vehicle-marker--offline': !vehicle.online }]"
      :style="markerStyle(vehicle)"
      :title="vehicleTitle(vehicle)"
      @click.stop="$emit('select-vehicle', vehicle)"
    >
      <span class="vehicle-marker__body" :style="{ transform: `rotate(${vehicle.heading || 0}deg)` }"></span>
      <span class="vehicle-marker__code">{{ vehicle.code.replace('FLC-', '') }}</span>
    </button>

    <div
      v-if="draftPoint"
      class="draft-point"
      :style="markerStyle(draftPoint)"
    ></div>

    <button
      v-for="corner in calibrationPoints"
      :key="corner.cornerKey"
      class="calibration-marker"
      :class="{ active: calibrationMode && activeCalibrationKey === corner.cornerKey }"
      :style="{ left: `${corner.x}%`, top: `${corner.y}%` }"
      :title="`${corner.label} | ${corner.lat || '-'}, ${corner.lng || '-'}`"
      @click.stop="$emit('select-calibration', corner)"
    >
      {{ corner.label.slice(0, 1) }}
    </button>

    <div class="map-scale">
      <span :style="{ width: `${scaleBarWidth}%` }"></span>
      <b>{{ scaleMeters }}m</b>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'

const props = defineProps({
  vehicles: { type: Array, default: () => [] },
  points: { type: Array, default: () => [] },
  editable: { type: Boolean, default: false },
  draftPoint: { type: Object, default: null },
  calibrationPoints: { type: Array, default: () => [] },
  calibrationMode: { type: Boolean, default: false },
  activeCalibrationKey: { type: String, default: '' },
  baseMode: { type: String, default: 'vector' },
  showLabels: { type: Boolean, default: true },
  scaleMeters: { type: Number, default: 50 },
  metersPerUnit: { type: Number, default: 6.5 },
  centerLat: { type: Number, default: 31.9438027 },
  centerLng: { type: Number, default: 120.9854705 },
  zoom: { type: Number, default: 17 },
})

const emit = defineEmits(['map-click', 'select-point', 'select-vehicle', 'select-calibration'])
const mapEl = ref(null)
const mapWidth = ref(920)
const mapHeight = ref(720)
let resizeObserver = null

const scaleBarWidth = computed(() => Math.max(4, Math.min(18, props.scaleMeters / props.metersPerUnit)))
const satelliteTiles = computed(() => buildTiles())

onMounted(() => {
  updateSize()
  if (window.ResizeObserver) {
    resizeObserver = new ResizeObserver(updateSize)
    resizeObserver.observe(mapEl.value)
  } else {
    window.addEventListener('resize', updateSize)
  }
})

onUnmounted(() => {
  if (resizeObserver) resizeObserver.disconnect()
  else window.removeEventListener('resize', updateSize)
})

function updateSize() {
  if (!mapEl.value) return
  const rect = mapEl.value.getBoundingClientRect()
  if (rect.width > 0) mapWidth.value = rect.width
  if (rect.height > 0) mapHeight.value = rect.height
}

function handleMapClick(event) {
  const rect = mapEl.value.getBoundingClientRect()
  const localX = event.clientX - rect.left
  const localY = event.clientY - rect.top
  const x = (localX / rect.width) * 100
  const y = (localY / rect.height) * 100
  const latLng = mapPixelToLatLng(localX, localY, rect.width, rect.height)
  emit('map-click', {
    x: Number(x.toFixed(2)),
    y: Number(y.toFixed(2)),
    lat: Number(latLng.lat.toFixed(7)),
    lng: Number(latLng.lng.toFixed(7)),
  })
}

function buildTiles() {
  const zoom = props.zoom
  const tileSize = 256
  const tileCount = 2 ** zoom
  const center = latLngToWorldPixel(props.centerLat, props.centerLng, zoom)
  const originX = center.x - mapWidth.value / 2
  const originY = center.y - mapHeight.value / 2
  const startX = Math.floor(originX / tileSize)
  const endX = Math.floor((originX + mapWidth.value) / tileSize)
  const startY = Math.floor(originY / tileSize)
  const endY = Math.floor((originY + mapHeight.value) / tileSize)
  const tiles = []

  for (let x = startX; x <= endX; x += 1) {
    for (let y = startY; y <= endY; y += 1) {
      if (y < 0 || y >= tileCount) continue
      const wrappedX = ((x % tileCount) + tileCount) % tileCount
      const server = Math.abs(x + y) % 4
      tiles.push({
        key: `${zoom}-${wrappedX}-${y}`,
        left: Math.round(x * tileSize - originX),
        top: Math.round(y * tileSize - originY),
        url: `https://mt${server}.google.com/vt/lyrs=s&x=${wrappedX}&y=${y}&z=${zoom}`,
      })
    }
  }
  return tiles
}

function latLngToWorldPixel(lat, lng, zoom) {
  const sinLat = Math.sin((Math.max(-85.05112878, Math.min(85.05112878, lat)) * Math.PI) / 180)
  const scale = 256 * 2 ** zoom
  return {
    x: ((lng + 180) / 360) * scale,
    y: (0.5 - Math.log((1 + sinLat) / (1 - sinLat)) / (4 * Math.PI)) * scale,
  }
}

function mapPixelToLatLng(localX, localY, width, height) {
  const zoom = props.zoom
  const scale = 256 * 2 ** zoom
  const center = latLngToWorldPixel(props.centerLat, props.centerLng, zoom)
  const worldX = center.x - width / 2 + localX
  const worldY = center.y - height / 2 + localY
  const lng = (worldX / scale) * 360 - 180
  const mercatorN = Math.PI - (2 * Math.PI * worldY) / scale
  const lat = (180 / Math.PI) * Math.atan(Math.sinh(mercatorN))
  return { lat, lng }
}

function optionalNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function firstNumber(...values) {
  for (const value of values) {
    const number = optionalNumber(value)
    if (number !== null) return number
  }
  return null
}

function latLngToMapPercent(lat, lng, width, height) {
  const center = latLngToWorldPixel(props.centerLat, props.centerLng, props.zoom)
  const point = latLngToWorldPixel(lat, lng, props.zoom)
  const originX = center.x - width / 2
  const originY = center.y - height / 2
  return {
    x: Math.max(0, Math.min(100, ((point.x - originX) / width) * 100)),
    y: Math.max(0, Math.min(100, ((point.y - originY) / height) * 100)),
  }
}

function markerStyle(entity) {
  const lat = firstNumber(entity.currentLat, entity.current_lat, entity.lat, entity.latitude)
  const lng = firstNumber(entity.currentLng, entity.current_lng, entity.lng, entity.longitude)
  if (lat !== null && lng !== null && !(lat === 0 && lng === 0)) {
    const mapped = latLngToMapPercent(lat, lng, mapWidth.value, mapHeight.value)
    return { left: `${mapped.x}%`, top: `${mapped.y}%` }
  }
  const x = firstNumber(entity.currentX, entity.current_x, entity.x, entity.mapX, entity.map_x) ?? 0
  const y = firstNumber(entity.currentY, entity.current_y, entity.y, entity.mapY, entity.map_y) ?? 0
  return { left: `${x}%`, top: `${y}%` }
}

function pointSymbol(type) {
  const dict = {
    pickup: '取',
    dropoff: '放',
    dock: '卸',
    charging: '充',
    maintenance: '修',
    parking: '停',
    lora: 'L',
    handover: '交',
    route: '路',
  }
  return dict[type] || '点'
}

function vehicleTitle(vehicle) {
  const driver = vehicle.driver?.name || '未绑定'
  return `${vehicle.code} | ${vehicle.status} | ${vehicle.currentArea} | ${driver} | ${vehicle.energyLevel}%`
}
</script>
