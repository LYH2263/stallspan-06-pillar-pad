<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
const data = ref<any>(null)
const vendors = ref<any[]>([])
async function run() { data.value = await api('/allocate/run?segment_id=1', { method: 'POST' }) }
onMounted(async () => {
  vendors.value = await api('/vendors')
  await run()
})
const colors = ['#e8a87c','#85dcb8','#e27d60','#c38d9e','#41b3a3','#f4a261','#e76f51']
// 主图只消费引擎结果：禁入带 / 摊位 / 空隙来自同一次运行的同一口径（厚度半宽 + 外扩），
// 图上柱侧空白端点与引擎禁入端点因此必然同数；前端不另算第二条口径
const cells = computed(() => {
  if (!data.value) return []
  const width = data.value.segment.width_m
  const out: any[] = []
  for (const b of data.value.blocked || []) {
    out.push({ type: 'pillar', start: b.start_m, end: b.end_m, label: '挡柱禁入带' })
  }
  for (const [i, p] of (data.value.placements || []).entries()) {
    out.push({ type: 'stall', start: p.start_m, end: p.end_m, label: p.vendor_name, color: colors[i % colors.length] })
  }
  for (const s of data.value.free_spans || []) {
    out.push({ type: 'gap', start: s.start_m, end: s.end_m, label: '空' })
  }
  return out.map(c => ({
    ...c,
    left: (c.start / width) * 100,
    pct: ((c.end - c.start) / width) * 100,
  }))
})
</script>
<template>
  <div class="ss-street-wrap">
    <h1>街段分配带</h1>
    <p class="sub">沿街一维开间 · 禁入带 = 厚度半宽 + 外扩 · 底部为摊主排队</p>
    <button class="btn" @click="run">重新分配</button>
    <div class="ss-band-ruler" v-if="data">
      <span>0 m</span>
      <span>{{ data.segment.name }} · {{ data.segment.width_m }} m</span>
      <span>{{ data.segment.width_m }} m</span>
    </div>
    <div class="ss-street-band" v-if="data">
      <div class="ss-street-inner">
        <div
          v-for="(c,i) in cells" :key="i"
          class="ss-band-cell"
          :class="{ 'ss-pillar': c.type === 'pillar', 'ss-gap': c.type === 'gap' }"
          :style="{ position: 'absolute', left: c.left + '%', width: c.pct + '%', background: c.type === 'stall' ? c.color : undefined }"
        >{{ c.label }}</div>
      </div>
    </div>
    <div class="ss-vendor-queue">
      <div v-for="v in vendors" :key="v.id" class="ss-vendor-chip">
        <strong>{{ v.name }}</strong>
        <span>需 {{ v.stall_width_m }} m · 优先 {{ v.priority }}</span>
      </div>
    </div>
    <div class="card" v-if="data">
      <table>
        <thead><tr><th>摊主</th><th>起点</th><th>终点</th><th>宽度</th></tr></thead>
        <tbody>
          <tr v-for="p in data.placements" :key="p.vendor_id">
            <td>{{ p.vendor_name }}</td><td>{{ p.start_m }}</td><td>{{ p.end_m }}</td><td>{{ p.width_m }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
