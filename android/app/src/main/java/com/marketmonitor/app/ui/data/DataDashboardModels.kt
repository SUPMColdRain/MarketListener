package com.marketmonitor.app.ui.data

/** One cleaned, finite point on a metric timeline. */
data class UiMetricPoint(
    val epochMillis: Long,
    val value: Double,
    val label: String,
)

/** A viewer-only metric series; raw data is never mutated or fabricated. */
data class UiMetricSeries(
    val seriesId: String,
    val name: String,
    val points: List<UiMetricPoint>,
    val latestValue: Double?,
    val latestLabel: String?,
)

enum class UiPanelKind {
    LINE_MULTI,
    AREA,
    HEATMAP,
    RANKING,
}

data class UiHeatmapCell(
    val row: String,
    val column: String,
    val value: Double,
    val normalized: Double,
)

data class UiRankingItem(
    val key: String,
    val label: String,
    val value: Double,
    val previousValue: Double?,
    val changePct: Double?,
)

data class UiRankingFrame(
    val dateLabel: String,
    val items: List<UiRankingItem>,
)

data class UiMetricPanel(
    val panelId: String,
    val title: String,
    val kind: UiPanelKind,
    val series: List<UiMetricSeries> = emptyList(),
    val heatmap: List<UiHeatmapCell> = emptyList(),
    val rankingFrames: List<UiRankingFrame> = emptyList(),
    val emptyReason: String? = null,
)

enum class UiMarketFilter(val label: String) {
    ALL("全市场"),
    A_SHARE("A股"),
    HONG_KONG("港股"),
    FUTURES("期货"),
    MACRO("宏观"),
}

enum class UiChartTimeRange(val label: String, val days: Int?) {
    MONTH_1("1M", 31),
    MONTH_3("3M", 92),
    MONTH_6("6M", 183),
    YEAR_1("1Y", 366),
    ALL("ALL", null),
}

data class DataDashboardUiState(
    val panels: List<UiMetricPanel> = emptyList(),
    val summary: String = "暂无已导入行情数据",
    val marketFilter: UiMarketFilter = UiMarketFilter.ALL,
    val timeRange: UiChartTimeRange = UiChartTimeRange.ALL,
) {
    val visiblePanels: List<UiMetricPanel>
        get() = panels.filter { panel ->
            when (panel.kind) {
                UiPanelKind.LINE_MULTI, UiPanelKind.AREA -> panel.series.isNotEmpty()
                UiPanelKind.HEATMAP -> panel.heatmap.isNotEmpty()
                UiPanelKind.RANKING -> panel.rankingFrames.isNotEmpty()
            }
        }
}
