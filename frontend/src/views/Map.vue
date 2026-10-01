<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import BlockedBand from '../components/BlockedBand.vue'
const data = ref<any>(null)
const vendors = ref<any[]>([])
const runId = ref<number | null>(null)
async function run() {
  const r = await api('/allocate/run?segment_id=1', { method: 'POST' })
  // 重新分配：整页只认本次提交瞬间算出的 blocked_zones（含最新外扩）
  data.value = r
  runId.value = r.id
}
onMounted(async () => {
  vendors.value = await api('/vendors')
  await run()
})
</script>
<template>
  <div class="ss-street-wrap">
    <h1>街段分配带</h1>
    <p class="sub">沿街一维开间 · 深色柱芯为挡柱厚度，橙色斜纹为厚度半宽＋外扩的连续禁入带 · 底部为摊主排队</p>
    <div>
      <button class="btn" @click="run">重新分配</button>
      <span v-if="runId" class="muted" style="margin-left:0.6rem">运行快照 #{{ runId }}</span>
    </div>
    <template v-if="data">
      <div class="ss-band-ruler">
        <span>0 m</span>
        <span>{{ data.segment.name }} · {{ data.segment.width_m }} m</span>
        <span>{{ data.segment.width_m }} m</span>
      </div>
      <!-- 柱侧空白端点与引擎禁入端点同源：直接画 run 快照里的 blocked_zones -->
      <BlockedBand :width-m="data.segment.width_m" :zones="data.blocked_zones || []" :placements="data.placements || []" />
    </template>
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
