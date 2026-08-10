<script setup lang="ts">
import { formatMoney, formatRevenue, textOrNone, type CompanyDetail } from "../domain/company";

defineProps<{ company: CompanyDetail }>();
</script>

<template>
  <section class="company-detail" :aria-label="`${company.name} F10`">
    <header class="company-heading">
      <div>
        <h2>{{ company.name }}</h2>
        <p>{{ company.code }} · {{ company.market }} · {{ company.instrumentKey }}</p>
      </div>
      <el-tag effect="dark">本地 F10</el-tag>
    </header>
    <p v-if="company.companyHighlight" class="company-highlight">{{ company.companyHighlight }}</p>
    <el-descriptions :column="1" border>
      <el-descriptions-item label="总市值">{{ formatMoney(company.totalMarketCap) }}</el-descriptions-item>
      <el-descriptions-item label="流通市值">{{ formatMoney(company.floatMarketCap) }}</el-descriptions-item>
      <el-descriptions-item label="公司简介">{{ textOrNone(company.companyIntro) }}</el-descriptions-item>
      <el-descriptions-item label="所属行业">{{ textOrNone(company.industry) }}</el-descriptions-item>
      <el-descriptions-item label="证监会行业">{{ textOrNone(company.csrcIndustry) }}</el-descriptions-item>
      <el-descriptions-item label="主营业务">{{ textOrNone(company.mainBusiness) }}</el-descriptions-item>
      <el-descriptions-item label="经营范围">{{ textOrNone(company.businessScope) }}</el-descriptions-item>
      <el-descriptions-item label="最赚钱业务">{{ formatRevenue(company.topRevenueSegment) }}</el-descriptions-item>
      <el-descriptions-item label="主要产品">
        <template v-if="company.products?.length"><el-tag v-for="product in company.products" :key="product" class="product-tag">{{ product }}</el-tag></template>
        <template v-else>暂无数据</template>
      </el-descriptions-item>
      <el-descriptions-item label="F10 来源 / 更新时间">{{ textOrNone(company.source) }} · {{ textOrNone(company.updatedAt) }}</el-descriptions-item>
      <el-descriptions-item label="产业链定位"><template v-if="company.chainLocations?.length"><el-tag v-for="location in company.chainLocations" :key="`${location.chain}-${location.stage}-${location.node}`" class="product-tag">{{ [location.chain, location.stage, location.node].filter(Boolean).join(' / ') }}</el-tag></template><template v-else>暂无数据</template></el-descriptions-item>
    </el-descriptions>
    <section class="revenue-section">
      <h3>收入构成</h3>
      <el-table v-if="company.revenueSegments?.length" :data="company.revenueSegments" size="small">
        <el-table-column prop="name" label="业务" min-width="150" />
        <el-table-column label="占比" width="100"><template #default="scope">{{ typeof scope.row.ratio === 'number' ? `${(scope.row.ratio * 100).toFixed(1)}%` : '暂无数据' }}</template></el-table-column>
        <el-table-column label="金额与日期" min-width="180"><template #default="scope">{{ formatMoney(scope.row.amount) }}</template></el-table-column>
      </el-table>
      <p v-else class="muted">暂无结构化收入构成。</p>
    </section>
  </section>
</template>
