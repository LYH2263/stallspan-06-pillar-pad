<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const drafts = ref<Record<number, string>>({})
const error = ref('')
const saving = ref<number | null>(null)

async function load() {
  rows.value = await api('/pillars')
  const d: Record<number, string> = {}
  for (const r of rows.value) d[r.id] = String(r.setback_m)
  drafts.value = d
}

async function save(r: any) {
  error.value = ''
  const v = Number(drafts.value[r.id])
  if (!Number.isFinite(v) || v < 0) {
    // 入口直接打回：不重载前列表保持改前数值
    error.value = `「${r.label}」外扩须为不小于 0 的数字，已打回`
    await load()
    return
  }
  saving.value = r.id
  try {
    await api(`/pillars/${r.id}`, { method: 'PUT', body: JSON.stringify({ setback_m: v }) })
    await load()
  } catch {
    // 后端打回：列表与图与拒绝名单与运行记录一律停在改前
    error.value = `「${r.label}」外扩提交被打回，已恢复改前数值`
    await load()
  } finally {
    saving.value = null
  }
}

onMounted(load)
</script>
<template>
  <h1>挡柱</h1>
  <p class="sub">街段障碍 · 禁入带 = 厚度半宽 + 外扩，与切空引擎 / 分配带 / 放不下同一口径</p>
  <div class="ss-street-band" style="height:90px;min-height:90px">
    <div class="ss-street-inner" style="gap:1rem;padding:0 1rem;align-items:center">
      <div
        v-for="r in rows" :key="r.id ?? JSON.stringify(r)"
        class="ss-band-cell ss-pillar"
        :style="{ width: Math.max((r.band_end_m - r.band_start_m) * 28, 36) + 'px', flex: '0 0 auto', height: '70%' }"
      >{{ r.label }} @{{ r.position_m }}m</div>
    </div>
  </div>
  <div class="card">
    <table>
      <thead><tr><th>名称</th><th>位置(m)</th><th>厚度(m)</th><th>外扩(m)</th><th>禁入带(m)</th><th></th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id ?? JSON.stringify(r)">
          <td>{{ r.label }}</td>
          <td>{{ r.position_m }}</td>
          <td>{{ r.thickness_m }}</td>
          <td>
            <input
              class="ss-input" type="number" min="0" step="0.1"
              v-model="drafts[r.id]" style="width:5.5rem"
            >
          </td>
          <td>{{ r.band_start_m }} ~ {{ r.band_end_m }}</td>
          <td><button class="btn" :disabled="saving === r.id" @click="save(r)">保存</button></td>
        </tr>
      </tbody>
    </table>
    <p v-if="error" class="ss-error">{{ error }}</p>
    <p class="muted" style="margin-bottom:0">外扩填 0 只按厚度；填负数直接打回。改外扩后到「分配带」重新分配即按新值画空隙。</p>
  </div>
</template>
