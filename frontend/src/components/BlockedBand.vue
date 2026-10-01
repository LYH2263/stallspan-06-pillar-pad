<script setup lang="ts">
// 柱侧空白（外扩带）+ 柱芯 + 摊位的唯一渲染组件。
// 所有端点直接取自后端引擎的 blocked_zones / placements，本组件不做任何
// thickness/2、±clearance 的几何计算，保证图上空白端点与引擎禁入端点同数。
const props = defineProps<{
  widthM: number
  zones: any[]
  placements?: any[]
  heightPx?: number
}>()
const colors = ['#e8a87c','#85dcb8','#e27d60','#c38d9e','#41b3a3','#f4a261','#e76f51']
function pct(m: number) {
  return props.widthM > 0 ? (m / props.widthM) * 100 : 0
}
function innerPct(coreM: number, z: any) {
  const span = z.end_m - z.start_m
  return span > 0 ? ((coreM - z.start_m) / span) * 100 : 0
}
function innerWidth(c: any, z: any) {
  const span = z.end_m - z.start_m
  return span > 0 ? ((c.core_end_m - c.core_start_m) / span) * 100 : 0
}
</script>
<template>
  <div class="ss-street-band" :style="heightPx ? { height: heightPx + 'px', minHeight: heightPx + 'px' } : undefined">
    <div class="ss-street-inner ss-absolute-band">
      <!-- 禁入带：厚度半宽 + 外扩；斜纹即柱侧空白，合法摊位不得吃进 -->
      <div
        v-for="(z, i) in zones" :key="'z' + i"
        class="ss-zone"
        :style="{ left: pct(z.start_m) + '%', width: pct(z.end_m - z.start_m) + '%' }"
        :title="`禁入带 ${z.start_m}–${z.end_m} m（厚度半宽＋外扩）`"
      >
        <span class="ss-zone-tag">禁入</span>
        <div
          v-for="(c, j) in z.pillars" :key="j"
          class="ss-band-cell ss-pillar ss-core"
          :style="{ left: innerPct(c.core_start_m, z) + '%', width: innerWidth(c, z) + '%' }"
          :title="`${c.label} 柱芯 ${c.core_start_m}–${c.core_end_m} m · 单侧外扩 ${c.clearance_m} m`"
        >{{ c.label }}</div>
      </div>
      <!-- 合法摊位只落在空档内 -->
      <div
        v-for="(p, i) in placements || []" :key="'p' + p.vendor_id"
        class="ss-band-cell ss-stall"
        :style="{ left: pct(p.start_m) + '%', width: pct(p.width_m) + '%', background: colors[i % colors.length] }"
      >{{ p.vendor_name }}</div>
    </div>
  </div>
</template>
