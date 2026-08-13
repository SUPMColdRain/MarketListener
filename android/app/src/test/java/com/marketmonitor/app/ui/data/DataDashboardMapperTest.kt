package com.marketmonitor.app.ui.data

import com.marketmonitor.app.data.MarketMetric
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class DataDashboardMapperTest {

    private fun metric(
        metricId: String,
        instrumentId: String,
        tradingDate: String,
        value: Double,
        metricName: String = "指标",
    ) = MarketMetric(
        metricId = metricId,
        instrumentId = instrumentId,
        tradingDate = tradingDate,
        period = "1d",
        metricName = metricName,
        value = value,
        definition = "",
        calculationMethod = "",
        timestamp = "${tradingDate}T15:00:00+08:00",
    )

    @Test
    fun nonFiniteValuesAreNeverTurnedIntoChartData() {
        val metrics = listOf(
            metric(
                "A_SHARE_BREADTH:CN.A_SHARE.BREADTH:2026-08-01:1d:ADVANCES",
                "CN.A_SHARE.BREADTH",
                "2026-08-01",
                Double.NaN,
                "上涨家数",
            ),
            metric(
                "A_SHARE_BREADTH:CN.A_SHARE.BREADTH:2026-08-02:1d:ADVANCES",
                "CN.A_SHARE.BREADTH",
                "2026-08-02",
                Double.POSITIVE_INFINITY,
                "上涨家数",
            ),
            metric(
                "A_SHARE_BREADTH:CN.A_SHARE.BREADTH:2026-08-03:1d:ADVANCES",
                "CN.A_SHARE.BREADTH",
                "2026-08-03",
                2800.0,
                "上涨家数",
            ),
        )

        val panels = DataDashboardMapper.buildPanels(metrics, UiMarketFilter.ALL, UiChartTimeRange.ALL)

        val breadth = panels.firstOrNull { it.panelId == "breadth" }
        assertNotNull(breadth)
        val series = breadth?.series
        assertEquals(1, series?.size)
        assertEquals(1, series?.first()?.points?.size)
        assertEquals(2800.0, series?.first()?.points?.first()?.value ?: 0.0, 0.0)
    }

    @Test
    fun downsampleKeepsFirstAndLastPoints() {
        val points = (0 until 1000).map { index ->
            UiMetricPoint(
                epochMillis = 1_700_000_000_000L + index,
                value = index.toDouble(),
                label = "p$index",
            )
        }

        val sampled = DataDashboardMapper.downsample(points, maxPoints = 300)

        assertEquals(300, sampled.size)
        assertEquals(points.first(), sampled.first())
        assertEquals(points.last(), sampled.last())
    }

    @Test
    fun timeRangeKeepsOnlyWindowEndingAtLatestPoint() {
        val series = DataDashboardMapper.seriesFor(
            listOf(
                metric(
                    "VIX:VIX:2026-01-01:DAILY:close",
                    "VIX",
                    "2026-01-01",
                    14.0,
                    "VIX",
                ),
                metric(
                    "VIX:VIX:2026-08-09:DAILY:close",
                    "VIX",
                    "2026-08-09",
                    16.0,
                    "VIX",
                ),
            ),
            setOf("VIX"),
            UiChartTimeRange.MONTH_1,
        )

        assertEquals(1, series.size)
        val points = series.first().points
        assertEquals(1, points.size)
        assertEquals("2026-08-09", points.first().label)
    }

    @Test
    fun rankingUsesOnlyRealDateFramesAndPreviousRealValues() {
        val metrics = listOf(
            metric(
                "FUTURES_OI_LEADERBOARD:AU:2026-08-01:1d:沪金持仓",
                "AU",
                "2026-08-01",
                100.0,
                "沪金",
            ),
            metric(
                "FUTURES_OI_LEADERBOARD:AG:2026-08-01:1d:沪银持仓",
                "AG",
                "2026-08-01",
                200.0,
                "沪银",
            ),
            metric(
                "FUTURES_OI_LEADERBOARD:AU:2026-08-02:1d:沪金持仓",
                "AU",
                "2026-08-02",
                150.0,
                "沪金",
            ),
            metric(
                "FUTURES_OI_LEADERBOARD:AG:2026-08-02:1d:沪银持仓",
                "AG",
                "2026-08-02",
                180.0,
                "沪银",
            ),
        )

        val frames = DataDashboardMapper.rankingFrames(metrics, UiChartTimeRange.ALL)

        assertEquals(2, frames.size)
        assertEquals(listOf("2026-08-01", "2026-08-02"), frames.map { it.dateLabel })
        val first = frames[0].items.sortedBy { it.key }
        assertEquals("AG", first[0].key)
        assertNull(first[0].changePct)
        val second = frames[1].items.associateBy { it.key }
        assertEquals(150.0, second["AU"]?.value ?: 0.0, 0.0)
        assertEquals(50.0, second["AU"]?.changePct ?: 0.0, 0.0)
        assertEquals(-10.0, second["AG"]?.changePct ?: 0.0, 0.0)
    }

    @Test
    fun rankingNeverFabricatesDatesOrInterpolatedValues() {
        val metrics = listOf(
            metric(
                "FUTURES_OI_LEADERBOARD:AU:2026-08-01:1d:沪金持仓",
                "AU",
                "2026-08-01",
                100.0,
                "沪金",
            ),
            metric(
                "FUTURES_OI_LEADERBOARD:AU:2026-08-03:1d:沪金持仓",
                "AU",
                "2026-08-03",
                300.0,
                "沪金",
            ),
        )

        val frames = DataDashboardMapper.rankingFrames(metrics, UiChartTimeRange.ALL)

        assertEquals(2, frames.size)
        assertEquals(listOf("2026-08-01", "2026-08-03"), frames.map { it.dateLabel })
        assertEquals(100.0, frames[0].items.first().value, 0.0)
        assertEquals(300.0, frames[1].items.first().value, 0.0)
    }

    @Test
    fun heatmapCellsNormalizeRealValuesWithinRange() {
        val metrics = listOf(
            metric(
                "FUTURES_OI_LEADERBOARD:AU:2026-08-01:1d:沪金持仓",
                "AU",
                "2026-08-01",
                100.0,
                "沪金",
            ),
            metric(
                "FUTURES_OI_LEADERBOARD:AG:2026-08-01:1d:沪银持仓",
                "AG",
                "2026-08-01",
                300.0,
                "沪银",
            ),
            metric(
                "FUTURES_OI_LEADERBOARD:AU:2026-08-02:1d:沪金持仓",
                "AU",
                "2026-08-02",
                200.0,
                "沪金",
            ),
            metric(
                "FUTURES_OI_LEADERBOARD:AG:2026-08-02:1d:沪银持仓",
                "AG",
                "2026-08-02",
                300.0,
                "沪银",
            ),
        )

        val cells = DataDashboardMapper.heatmapCells(metrics, UiChartTimeRange.ALL)

        assertEquals(4, cells.size)
        cells.forEach { cell ->
            assertTrue("normalized in range", cell.normalized in 0.0..1.0)
        }
        assertEquals(0.0, cells.first { it.row == "AU" && it.column == "2026-08-01" }.normalized, 0.0)
        assertEquals(1.0, cells.first { it.row == "AG" && it.column == "2026-08-01" }.normalized, 0.0)
    }

    @Test
    fun emptyPanelsAreHiddenNotShownAsZero() {
        val panels = DataDashboardMapper.buildPanels(emptyList(), UiMarketFilter.ALL, UiChartTimeRange.ALL)
        assertTrue(panels.isEmpty())
        val state = DataDashboardMapper.buildState(
            metrics = emptyList(),
            summary = "暂无已导入行情数据",
            marketFilter = UiMarketFilter.ALL,
            timeRange = UiChartTimeRange.ALL,
        )
        assertTrue(state.visiblePanels.isEmpty())
        assertEquals("暂无已导入行情数据", state.summary)
    }

    @Test
    fun knownFuturesGroupIsNotSwallowedByOtherPanel() {
        val metrics = listOf(
            metric(
                "FUTURE_GLOBAL_BAR:NYMEX.CL:2026-08-01:1d:WTI",
                "NYMEX.CL",
                "2026-08-01",
                75.0,
                "WTI原油",
            ),
        )

        val panels = DataDashboardMapper.buildPanels(metrics, UiMarketFilter.FUTURES, UiChartTimeRange.ALL)

        assertFalse(panels.any { it.panelId == "other" })
        assertTrue(panels.any { it.panelId == "global" })
    }
}
