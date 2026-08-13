package com.marketmonitor.app.ui.data

import com.marketmonitor.app.data.MarketMetric
import com.marketmonitor.app.data.groupKeyFor
import com.marketmonitor.app.data.seriesIdOf
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.ZoneOffset

/**
 * Pure mapper from raw imported market metrics to viewer-only dashboard
 * panels. Missing, failed or non-finite values are never fabricated as zero;
 * panels with no real data simply carry an empty reason.
 */
object DataDashboardMapper {

    const val MAX_POINTS_PER_SERIES = 300
    private const val MAX_RANKING_ITEMS = 12
    private const val MAX_HEATMAP_ROWS = 12
    private const val MAX_HEATMAP_COLUMNS = 24

    fun buildState(
        metrics: List<MarketMetric>,
        summary: String,
        marketFilter: UiMarketFilter,
        timeRange: UiChartTimeRange,
    ): DataDashboardUiState {
        val panels = buildPanels(metrics, marketFilter, timeRange)
        return DataDashboardUiState(
            panels = panels,
            summary = summary,
            marketFilter = marketFilter,
            timeRange = timeRange,
        )
    }

    fun buildPanels(
        metrics: List<MarketMetric>,
        marketFilter: UiMarketFilter,
        timeRange: UiChartTimeRange,
    ): List<UiMetricPanel> {
        val finite = metrics.filter { it.value.isFinite() }
        val filtered = finite.filter { metric -> marketFilter.accepts(groupKeyFor(metric.metricId)) }

        val breadth = seriesFor(filtered, setOf("A_SHARE_BREADTH", "CN_ZT_POOL"), timeRange)
        val funding = seriesFor(filtered, setOf("HSGT_FLOW", "CN_MARGIN"), timeRange)
        val macro = seriesFor(
            filtered,
            setOf(
                "M1_MONEY_SUPPLY",
                "M2_MONEY_SUPPLY",
                "DR007",
                "CPI",
                "PPI",
                "CPI_PPI_SPREAD",
                "PMI_MANUFACTURING",
                "PMI_SERVICES",
                "PMI_CAIXIN_MANUFACTURING",
                "PMI_CAIXIN_SERVICES",
                "FED_FUNDS_RATE",
                "USD_INDEX",
                "VIX",
                "CN10Y_YIELD",
                "US10Y_YIELD",
            ),
            timeRange,
        )
        val global = seriesFor(
            filtered,
            setOf("GOLD_SILVER_RATIO", "GOLD_OIL_RATIO", "BTC_USD", "ETH_USD", "FUTURE_GLOBAL_BAR"),
            timeRange,
        )
        val futuresBreadth = seriesFor(filtered, setOf("FUTURES_BREADTH"), timeRange)
        val other = seriesFor(filtered, emptySet(), timeRange, includeRemaining = true)

        val rankingAndHeatmap = buildFuturesPanels(filtered, timeRange)

        return listOfNotNull(
            UiMetricPanel(
                panelId = "breadth",
                title = "市场广度",
                kind = UiPanelKind.LINE_MULTI,
                series = breadth,
                emptyReason = "暂无该指标数据",
            ).takeIf { breadth.isNotEmpty() },
            UiMetricPanel(
                panelId = "funding",
                title = "资金与情绪",
                kind = UiPanelKind.AREA,
                series = funding,
                emptyReason = "暂无该指标数据",
            ).takeIf { funding.isNotEmpty() },
            UiMetricPanel(
                panelId = "futures_breadth",
                title = "期货涨跌",
                kind = UiPanelKind.LINE_MULTI,
                series = futuresBreadth,
                emptyReason = "暂无该指标数据",
            ).takeIf { futuresBreadth.isNotEmpty() },
            rankingAndHeatmap?.first,
            rankingAndHeatmap?.second,
            UiMetricPanel(
                panelId = "macro",
                title = "宏观与波动率",
                kind = UiPanelKind.LINE_MULTI,
                series = macro,
                emptyReason = "暂无该指标数据",
            ).takeIf { macro.isNotEmpty() },
            UiMetricPanel(
                panelId = "global",
                title = "全球资产",
                kind = UiPanelKind.AREA,
                series = global,
                emptyReason = "暂无该指标数据",
            ).takeIf { global.isNotEmpty() },
            UiMetricPanel(
                panelId = "other",
                title = "其他指标",
                kind = UiPanelKind.LINE_MULTI,
                series = other,
                emptyReason = "暂无该指标数据",
            ).takeIf { other.isNotEmpty() },
        )
    }

    /** Builds one series per metric series id, sorted by time and downsampled for viewing. */
    fun seriesFor(
        metrics: List<MarketMetric>,
        groupKeys: Set<String>,
        timeRange: UiChartTimeRange,
        includeRemaining: Boolean = false,
    ): List<UiMetricSeries> {
        val buckets = linkedMapOf<String, MutableList<MarketMetric>>()
        for (metric in metrics) {
            val groupKey = groupKeyFor(metric.metricId)
            if (groupKey in groupKeys || (includeRemaining && groupKeys.isEmpty() && groupKey !in KNOWN_PANEL_GROUPS)) {
                buckets.getOrPut(seriesIdOf(metric)) { mutableListOf() }.add(metric)
            }
        }

        val series = buckets.mapNotNull { (seriesId, samples) ->
            val points = samples
                .mapNotNull { sample -> pointOf(sample) }
                .sortedBy { it.epochMillis }
            if (points.isEmpty()) {
                null
            } else {
                val name = samples.first().metricName.ifBlank { seriesId }
                UiMetricSeries(
                    seriesId = seriesId,
                    name = name,
                    points = downsample(applyRange(points, timeRange)),
                    latestValue = points.last().value,
                    latestLabel = points.last().label,
                )
            }
        }.sortedBy { it.name }

        return series
    }

    /** Real ranking frames grouped by trading date; UI only animates between real frames. */
    fun rankingFrames(metrics: List<MarketMetric>, timeRange: UiChartTimeRange): List<UiRankingFrame> {
        val byDate = metrics
            .filter { it.value.isFinite() && it.metricId.startsWith("FUTURES_OI_LEADERBOARD") }
            .groupBy { it.tradingDate }
            .toSortedMap()

        val dates = byDate.keys.toList()
        if (dates.isEmpty()) return emptyList()
        val maxEpoch = dates.maxOf { epochOfDate(it) }
        val minEpoch = timeRange.days?.let { maxEpoch - it * 86_400_000L } ?: Long.MIN_VALUE

        var previous: Map<String, Double> = emptyMap()
        return dates.mapNotNull { date ->
            if (epochOfDate(date) < minEpoch) {
                previous = emptyMap()
                null
            } else {
                val frame = buildRankingFrame(date, byDate[date].orEmpty(), previous)
                previous = frame.items.associate { it.key to it.value }
                frame
            }
        }
    }

    /** Heatmap of real futures open-interest values (rows = instruments, columns = dates). */
    fun heatmapCells(metrics: List<MarketMetric>, timeRange: UiChartTimeRange): List<UiHeatmapCell> {
        val relevant = metrics
            .filter { it.value.isFinite() && it.metricId.startsWith("FUTURES_OI_LEADERBOARD") }
        if (relevant.isEmpty()) return emptyList()

        val latestDate = relevant.maxOfOrNull { it.tradingDate } ?: return emptyList()
        val maxEpoch = epochOfDate(latestDate)
        val minEpoch = timeRange.days?.let { maxEpoch - it * 86_400_000L } ?: Long.MIN_VALUE

        val byDate = relevant
            .filter { epochOfDate(it.tradingDate) >= minEpoch }
            .groupBy { it.tradingDate }
            .toSortedMap()
        if (byDate.isEmpty()) return emptyList()

        val dates = byDate.keys.toList().takeLast(MAX_HEATMAP_COLUMNS)
        val latestValues = byDate[dates.last()].orEmpty()
            .associate { it.instrumentId to it.value }
        val rows = latestValues.entries
            .sortedByDescending { it.value }
            .take(MAX_HEATMAP_ROWS)
            .map { it.key }

        val cells = mutableListOf<UiHeatmapCell>()
        val allValues = mutableListOf<Double>()
        for (rowIndex in rows.indices) {
            for (columnIndex in dates.indices) {
                val sample = byDate[dates[columnIndex]].orEmpty()
                    .firstOrNull { it.instrumentId == rows[rowIndex] }
                if (sample != null) {
                    cells += UiHeatmapCell(
                        row = rows[rowIndex],
                        column = dates[columnIndex],
                        value = sample.value,
                        normalized = 0.0,
                    )
                    allValues += sample.value
                }
            }
        }
        if (cells.isEmpty()) return emptyList()

        val min = allValues.min()
        val max = allValues.max()
        val span = (max - min).takeIf { it > 0.0 } ?: 1.0
        return cells.map { cell ->
            cell.copy(normalized = ((cell.value - min) / span).coerceIn(0.0, 1.0))
        }
    }

    /** Evenly-spaced viewer downsampling; first and last points are always kept. */
    fun downsample(points: List<UiMetricPoint>, maxPoints: Int = MAX_POINTS_PER_SERIES): List<UiMetricPoint> {
        if (points.size <= maxPoints || maxPoints <= 1) return points
        return (0 until maxPoints).map { index ->
            val sourceIndex = (index.toLong() * (points.size - 1) / (maxPoints - 1)).toInt()
            points[sourceIndex]
        }
    }

    private fun buildFuturesPanels(
        metrics: List<MarketMetric>,
        timeRange: UiChartTimeRange,
    ): Pair<UiMetricPanel, UiMetricPanel>? {
        val frames = rankingFrames(metrics, timeRange)
        val heatmap = heatmapCells(metrics, timeRange)
        if (frames.isEmpty() && heatmap.isEmpty()) return null

        val rankingPanel = UiMetricPanel(
            panelId = "futures_ranking",
            title = "期货持仓排名",
            kind = UiPanelKind.RANKING,
            rankingFrames = frames,
            emptyReason = "暂无该指标数据",
        )
        val heatmapPanel = UiMetricPanel(
            panelId = "futures_heatmap",
            title = "期货持仓热力图",
            kind = UiPanelKind.HEATMAP,
            heatmap = heatmap,
            emptyReason = "暂无该指标数据",
        )
        return rankingPanel to heatmapPanel
    }

    private fun buildRankingFrame(
        date: String,
        samples: List<MarketMetric>,
        previous: Map<String, Double>,
    ): UiRankingFrame {
        val items = samples
            .groupBy { it.instrumentId }
            .map { (instrumentId, group) ->
                val latest = group.maxByOrNull { it.timestamp } ?: return@map null
                val previousValue = previous[instrumentId]
                UiRankingItem(
                    key = instrumentId,
                    label = latest.metricName.ifBlank { instrumentId },
                    value = latest.value,
                    previousValue = previousValue,
                    changePct = percentChange(previousValue, latest.value),
                )
            }
            .filterNotNull()
            .sortedByDescending { it.value }
            .take(MAX_RANKING_ITEMS)
        return UiRankingFrame(dateLabel = date, items = items)
    }

    private fun percentChange(previous: Double?, current: Double): Double? {
        if (previous == null || previous == 0.0) return null
        return (current - previous) / previous * 100.0
    }

    private fun pointOf(metric: MarketMetric): UiMetricPoint? {
        val epoch = epochOf(metric) ?: return null
        if (!metric.value.isFinite()) return null
        return UiMetricPoint(
            epochMillis = epoch,
            value = metric.value,
            label = metric.tradingDate,
        )
    }

    private fun epochOf(metric: MarketMetric): Long? {
        if (metric.timestamp.isNotBlank()) {
            runCatching { return OffsetDateTime.parse(metric.timestamp).toInstant().toEpochMilli() }
        }
        return runCatching { epochOfDate(metric.tradingDate) }.getOrNull()
    }

    private fun epochOfDate(date: String): Long =
        LocalDate.parse(date).atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli()

    private fun applyRange(
        points: List<UiMetricPoint>,
        timeRange: UiChartTimeRange,
    ): List<UiMetricPoint> {
        val days = timeRange.days ?: return points
        val maxEpoch = points.maxOfOrNull { it.epochMillis } ?: return points
        val minEpoch = maxEpoch - days * 86_400_000L
        return points.filter { it.epochMillis >= minEpoch }
    }

    private val KNOWN_PANEL_GROUPS = setOf(
        "A_SHARE_BREADTH",
        "CN_ZT_POOL",
        "HSGT_FLOW",
        "CN_MARGIN",
        "FUTURES_BREADTH",
        "FUTURES_OI_LEADERBOARD",
        "M1_MONEY_SUPPLY",
        "M2_MONEY_SUPPLY",
        "DR007",
        "CPI",
        "PPI",
        "CPI_PPI_SPREAD",
        "PMI_MANUFACTURING",
        "PMI_SERVICES",
        "PMI_CAIXIN_MANUFACTURING",
        "PMI_CAIXIN_SERVICES",
        "FED_FUNDS_RATE",
        "USD_INDEX",
        "VIX",
        "CN10Y_YIELD",
        "US10Y_YIELD",
        "GOLD_SILVER_RATIO",
        "GOLD_OIL_RATIO",
        "BTC_USD",
        "ETH_USD",
        "FUTURE_GLOBAL_BAR",
    )
}

private fun UiMarketFilter.accepts(groupKey: String): Boolean = when (this) {
    UiMarketFilter.ALL -> true
    UiMarketFilter.A_SHARE -> groupKey in A_SHARE_GROUPS
    UiMarketFilter.HONG_KONG -> groupKey == "HSGT_FLOW"
    UiMarketFilter.FUTURES -> groupKey in FUTURES_GROUPS
    UiMarketFilter.MACRO -> groupKey in MACRO_GROUPS
}

private val A_SHARE_GROUPS = setOf(
    "A_SHARE_BREADTH",
    "CN_ZT_POOL",
    "CN_MARGIN",
    "HSGT_FLOW",
)

private val FUTURES_GROUPS = setOf(
    "FUTURES_BREADTH",
    "FUTURES_OI_LEADERBOARD",
    "FUTURE_GLOBAL_BAR",
)

private val MACRO_GROUPS = setOf(
    "M1_MONEY_SUPPLY",
    "M2_MONEY_SUPPLY",
    "DR007",
    "CPI",
    "PPI",
    "CPI_PPI_SPREAD",
    "PMI_MANUFACTURING",
    "PMI_SERVICES",
    "PMI_CAIXIN_MANUFACTURING",
    "PMI_CAIXIN_SERVICES",
    "FED_FUNDS_RATE",
    "USD_INDEX",
    "VIX",
    "CN10Y_YIELD",
    "US10Y_YIELD",
    "GOLD_SILVER_RATIO",
    "GOLD_OIL_RATIO",
)
