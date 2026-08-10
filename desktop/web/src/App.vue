<script setup lang="ts">
const navigation = [
  ["/", "首页"],
  ["/data/", "数据"],
  ["/f10/", "F10"],
  ["/industry/", "产业链图谱"],
  ["/logs/", "日志"],
] as const;
</script>

<template>
  <el-container class="terminal">
    <el-header class="topbar">
      <router-link class="brand" to="/">MarketListener</router-link>
      <nav aria-label="主导航">
        <router-link v-for="[path, label] in navigation" :key="path" :to="path">{{ label }}</router-link>
      </nav>
      <span class="mode">LOCAL RESEARCH TERMINAL</span>
    </el-header>
    <el-main><router-view /></el-main>
  </el-container>
</template>
