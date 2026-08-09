package com.marketmonitor.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.marketmonitor.app.data.ImportedMarketData
import com.marketmonitor.app.data.MetricGroup
import com.marketmonitor.app.data.aggregateMetrics
import com.marketmonitor.app.data.filterMetrics
import com.marketmonitor.app.data.formatMetricValue

@Composable
fun DataScreen(marketData: ImportedMarketData?) {
    var query by remember { mutableStateOf("") }
    val allMetrics = marketData?.metrics.orEmpty()
    val visibleMetrics = remember(allMetrics, query) { filterMetrics(allMetrics, query) }
    val groups = remember(visibleMetrics) { aggregateMetrics(visibleMetrics) }

    Column(
        modifier = Modifier.fillMaxSize().statusBarsPadding().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("数据中心", style = MaterialTheme.typography.titleLarge)
        OutlinedCard(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(12.dp)) {
                Text("同步包", style = MaterialTheme.typography.labelLarge)
                Text(
                    marketData?.packageId ?: "无已导入行情包",
                    style = MaterialTheme.typography.bodyMedium,
                )
                Text("数据截止", style = MaterialTheme.typography.labelLarge)
                Text(
                    marketData?.dataCutoff ?: "暂无",
                    style = MaterialTheme.typography.bodyMedium,
                )
                Text("指标行数：${allMetrics.size}", style = MaterialTheme.typography.bodyMedium)
            }
        }
        OutlinedTextField(
            value = query,
            onValueChange = { query = it },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            label = { Text("搜索指标（名称/代码）") },
            placeholder = { Text("例如：融资、涨停、PMI、VIX") },
        )
        if (visibleMetrics.isEmpty()) {
            OutlinedCard(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Text(
                        if (allMetrics.isEmpty()) {
                            "尚未同步指标数据。请先在“行情”页从电脑同步行情包，或导入包含 gold_metrics 的行情包。"
                        } else {
                            "没有匹配“$query”的指标。"
                        },
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            }
        } else {
            LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                items(groups, key = { it.key }) { group ->
                    MetricGroupCard(group)
                }
            }
        }
    }
}

@Composable
private fun MetricGroupCard(group: MetricGroup) {
    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(
                "${group.label}（${group.series.size} 个系列）",
                style = MaterialTheme.typography.titleSmall,
            )
            group.series.forEach { series ->
                Row(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(series.metricName, style = MaterialTheme.typography.bodyMedium)
                        Text(
                            "${series.latest.tradingDate} · ${series.sampleCount} 期",
                            style = MaterialTheme.typography.labelSmall,
                        )
                    }
                    Text(
                        formatMetricValue(series.latest.value),
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            }
        }
    }
}
