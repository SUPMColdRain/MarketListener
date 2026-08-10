package com.marketmonitor.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.marketmonitor.app.data.ImportedMarketData
import com.marketmonitor.app.data.filterMetrics
import com.marketmonitor.app.ui.chart.EChartsOptionBuilder
import com.marketmonitor.app.ui.chart.EChartsView
import com.marketmonitor.app.ui.chart.AnimatedRanking
import com.marketmonitor.app.ui.chart.rememberChartTheme
import com.marketmonitor.app.ui.data.DataDashboardViewModel
import com.marketmonitor.app.ui.data.UiChartTimeRange
import com.marketmonitor.app.ui.data.UiMarketFilter
import com.marketmonitor.app.ui.data.UiMetricPanel
import com.marketmonitor.app.ui.data.UiPanelKind
import com.marketmonitor.app.ui.theme.MarketTheme

/**
 * Quant dashboard: chart-first data browser over the imported market snapshot.
 * Panels only appear when real data exists; missing data never renders as 0.
 */
@Composable
fun DataScreen(marketData: ImportedMarketData?) {
    val viewModel: DataDashboardViewModel = viewModel()
    var query by rememberSaveable { mutableStateOf("") }
    var marketFilter by rememberSaveable { mutableStateOf(UiMarketFilter.ALL) }
    var timeRange by rememberSaveable { mutableStateOf(UiChartTimeRange.ALL) }

    val allMetrics = remember(marketData) { marketData?.metrics.orEmpty() }
    val summary = remember(marketData) {
        if (marketData == null) {
            "无已导入行情包"
        } else {
            "同步包 ${marketData.packageId} · 截止 ${marketData.dataCutoff} · ${allMetrics.size} 个指标"
        }
    }
    val visibleMetrics = remember(allMetrics, query) { filterMetrics(allMetrics, query) }

    LaunchedEffect(visibleMetrics, summary, marketFilter, timeRange) {
        viewModel.refresh(visibleMetrics, summary, marketFilter, timeRange)
    }
    val state by viewModel.state.collectAsState()

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item {
            Text(
                text = summary,
                style = MaterialTheme.typography.bodySmall,
                color = MarketTheme.colors.flat,
                modifier = Modifier.padding(horizontal = MarketTheme.dimensions.spacingMedium),
            )
        }
        item {
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = MarketTheme.dimensions.spacingMedium),
                singleLine = true,
                label = { Text("搜索指标（名称/代码）") },
                placeholder = { Text("例如：融资、涨停、PMI、VIX") },
            )
        }
        item {
            FilterRow(
                items = UiMarketFilter.entries,
                label = { it.label },
                selected = marketFilter,
                onSelect = { marketFilter = it },
            )
        }
        item {
            FilterRow(
                items = UiChartTimeRange.entries,
                label = { it.label },
                selected = timeRange,
                onSelect = { timeRange = it },
            )
        }
        if (state.visiblePanels.isEmpty()) {
            item {
                Text(
                    text = if (allMetrics.isEmpty()) {
                        "尚未同步指标数据。请先在“行情”页从电脑同步行情包，或导入包含 gold_metrics 的行情包。"
                    } else {
                        "没有匹配“$query”的指标。"
                    },
                    style = MaterialTheme.typography.bodyMedium,
                    color = MarketTheme.colors.flat,
                    modifier = Modifier.padding(MarketTheme.dimensions.spacingMedium),
                )
            }
        } else {
            items(state.visiblePanels, key = { it.panelId }) { panel ->
                PanelSection(panel)
            }
        }
    }
}

@Composable
private fun <T> FilterRow(
    items: List<T>,
    label: (T) -> String,
    selected: T,
    onSelect: (T) -> Unit,
) {
    LazyRow(
        contentPadding = androidx.compose.foundation.layout.PaddingValues(
            horizontal = MarketTheme.dimensions.spacingMedium,
        ),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        items(items) { item ->
            FilterChip(
                selected = item == selected,
                onClick = { onSelect(item) },
                label = { Text(label(item), style = MaterialTheme.typography.labelSmall) },
            )
        }
    }
}

@Composable
private fun PanelSection(panel: UiMetricPanel) {
    val chartTheme = rememberChartTheme()
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = MarketTheme.dimensions.spacingMedium),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text(panel.title, style = MaterialTheme.typography.titleSmall)
        when (panel.kind) {
            UiPanelKind.LINE_MULTI -> EChartsView(
                optionJson = EChartsOptionBuilder.buildLineOption(panel.series, chartTheme, area = false),
                height = 200.dp,
            )
            UiPanelKind.AREA -> EChartsView(
                optionJson = EChartsOptionBuilder.buildLineOption(panel.series, chartTheme, area = true),
                height = 200.dp,
            )
            UiPanelKind.HEATMAP -> EChartsView(
                optionJson = EChartsOptionBuilder.buildHeatmapOption(panel, chartTheme),
                height = 260.dp,
            )
            UiPanelKind.RANKING -> AnimatedRanking(panel.rankingFrames)
        }
    }
}
