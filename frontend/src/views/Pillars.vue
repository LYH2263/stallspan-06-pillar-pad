<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import BlockedBand from '../components/BlockedBand.vue'
const rows = ref<any[]>([])
const zones = ref<any[]>([])
const widthM = ref(30)
const drafts = ref<Record<number, string>>({})
const errors = ref<Record<number, string>>({})
const saving = ref<number | null>(null)

// 柱 → 所属合并禁入带的端点，全部取自引擎输出，前端不做厚度/外扩算术
const zoneByPillar = ref<Record<number, any>>({})

async function refresh() {
  // 列表与柱侧空白同源同刻重取，避免一个按新外扩、一个按旧外扩
  const [list, zonesData] = await Promise.all([
    api('/pillars'),
    api('/pillars/blocked-zones?segment_id=1'),
  ])
  rows.value = list
  widthM.value = zonesData.width_m
  zones.value = zonesData.blocked_zones
  const map: Record<number, any> = {}
  for (const z of zones.value) {
    for (const c of z.pillars || []) {
      if (c.pillar_id != null) map[c.pillar_id] = z
    }
  }
  zoneByPillar.value = map
  for (const r of rows.value) drafts.value[r.id] = String(r.clearance_m ?? 0)
  errors.value = {}
}

async function save(r: any) {
  const raw = (drafts.value[r.id] ?? '').trim()
  const value = Number(raw)
  // 入口直接打回：负数/非数字不提交，列表与图一律停在改前
  if (raw === '' || !Number.isFinite(value)) {
    errors.value[r.id] = '外扩必须是数字（米）'
    drafts.value[r.id] = String(r.clearance_m ?? 0)
    return
  }
  if (value < 0) {
    errors.value[r.id] = '外扩不得为负，已停在改前值'
    drafts.value[r.id] = String(r.clearance_m ?? 0)
    return
  }
  errors.value[r.id] = ''
  saving.value = r.id
  try {
    await api('/pillars/' + r.id, {
      method: 'PUT',
      body: JSON.stringify({ clearance_m: value }),
    })
    await refresh() // 提交后再进列表保留新值，柱侧空白按提交瞬间新值重画
  } catch (e: any) {
    errors.value[r.id] = '服务器打回：' + (e.message || '保存失败')
    drafts.value[r.id] = String(r.clearance_m ?? 0)
  } finally {
    saving.value = null
  }
}

onMounted(refresh)
</script>
<template>
  <h1>挡柱</h1>
  <p class="sub">每根挡柱在厚度之外可登记单侧外扩米数；柱侧空白与切空引擎共用「厚度半宽＋外扩」禁入带，邻柱外扩相交即合并</p>
  <BlockedBand :width-m="widthM" :zones="zones" :height-px="110" />
  <div class="card">
    <table>
      <thead><tr><th>名称</th><th>位置(m)</th><th>厚度(m)</th><th>单侧外扩(m)</th><th>已提交禁入带端点(m)</th><th></th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id">
          <td>{{ r.label }}</td>
          <td>{{ r.position_m }}</td>
          <td>{{ r.thickness_m }}</td>
          <td>
            <input
              v-model="drafts[r.id]"
              type="number"
              step="0.05"
              min="0"
              style="width:6.5rem"
              :aria-label="r.label + ' 外扩米数'"
            />
            <div v-if="errors[r.id]" class="ss-field-error">{{ errors[r.id] }}</div>
          </td>
          <td class="muted">
            <template v-if="zoneByPillar[r.id]">
              {{ zoneByPillar[r.id].start_m }} – {{ zoneByPillar[r.id].end_m }}
            </template>
          </td>
          <td><button class="btn" :disabled="saving === r.id" @click="save(r)">提交</button></td>
        </tr>
      </tbody>
    </table>
    <p class="muted" style="margin-bottom:0">外扩填 0 只按厚度（与绿仓相同）；填负数入口直接打回，列表、主图、放不下与运行快照均停在改前。</p>
  </div>
</template>
