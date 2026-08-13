package com.marketmonitor.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class MetricGroupsTest {

    private fun metric(
        metricId: String,
        metricName: String,
        tradingDate: String,
        value: Double,
    ) = MarketMetric(
        metricId = metricId,
        instrumentId = "fixture",
        tradingDate = tradingDate,
        period = "1d",
        metricName = metricName,
        value = value,
        definition = "",
        calculationMethod = "",
        timestamp = "2026-08-07T15:00:00+08:00",
    )

    @Test
    fun groupsKnownMetricsBySeriesAndKeepsLatest() {
        val groups = aggregateMetrics(
            listOf(
                metric("CN_MARGIN:CN.SSE.MARGIN:20260806:1d:融资余额", "沪市融资余额", "20260806", 100.0),
                metric("CN_MARGIN:CN.SSE.MARGIN:20260807:1d:融资余额", "沪市融资余额", "20260807", 120.0),
                metric("A_SHARE_BREADTH:CN.A_SHARE.BREADTH:2026-08-07:1d:ADVANCES", "上涨家数", "2026-08-07", 2856.0),
            ),
        )

        assertEquals(2, groups.size)
        assertEquals("融资融券（沪/深/京）", groups[0].label)
        assertEquals(1, groups[0].series.size)
        assertEquals(120.0, groups[0].series[0].latest.value, 0.0)
        assertEquals(2, groups[0].series[0].sampleCount)
        assertEquals("A股情绪与市场宽度", groups[1].label)
    }

    @Test
    fun unknownMetricsFallBackToPrefixLabel() {
        val groups = aggregateMetrics(
            listOf(metric("SOME_NEW_SERIES:ABC:20260807:1d:VALUE", "新指标", "20260807", 1.0)),
        )

        assertEquals(1, groups.size)
        assertEquals("SOME_NEW_SERIES", groups[0].label)
    }

    @Test
    fun filterMatchesChineseNameCodeAndDefinition() {
        val metrics = listOf(
            metric("CN_MARGIN:CN.SSE.MARGIN:20260807:1d:融资余额", "沪市融资余额", "20260807", 1.0),
            metric("VIX:VIX:2026-08-07:DAILY:close", "VIX 波动率指数", "2026-08-07", 14.9),
            metric("BTC_USD:BTC_USD:2026-08-07:DAILY:close", "比特币价格", "2026-08-07", 64923.19),
        )

        assertEquals(1, filterMetrics(metrics, "融资").size)
        assertEquals(1, filterMetrics(metrics, "VIX").size)
        assertEquals(0, filterMetrics(metrics, "不存在的指标").size)
        assertEquals(3, filterMetrics(metrics, "  ").size)
    }

    @Test
    fun formatsValuesWithoutTrailingZeros() {
        assertEquals("123", formatMetricValue(123.0))
        assertEquals("123.45", formatMetricValue(123.45))
        assertEquals("0.1234", formatMetricValue(0.1234))
        assertTrue(formatMetricValue(64923.19).startsWith("64923.19"))
    }
}
