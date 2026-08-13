package com.marketmonitor.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ImportedMarketDataTest {
    @Test
    fun decodesNormalizedBarForOfflineCharting() {
        val candle = decodeMarketCandle(
            """{"bar_open_time":"2026-08-03T09:30:00+08:00","open":10.0,"high":11.0,"low":9.5,"close":10.5,"source":{"provider":"fixture"},"quality_status":"PASS"}""",
        )

        requireNotNull(candle)
        assertEquals(1_785_720_600L, candle.openTimeSeconds)
        assertEquals(10.5, candle.close, 0.0)
        assertEquals("fixture", candle.source)
        assertEquals("PASS", candle.qualityStatus)
    }

    @Test
    fun rejectsMalformedBarWithoutCreatingChartData() {
        assertNull(decodeMarketCandle("{bad json"))
    }

    @Test
    fun decodesGoldMetricForDataPage() {
        val metric = decodeMarketMetric(
            """{"metric_id":"CN_MARGIN:CN.SSE.MARGIN:20260807:1d:融资余额","instrument_id":"CN.SSE.MARGIN","trading_date":"20260807","period":"1d","metric_name":"沪市融资余额","value":1266993136806.0,"definition":"融资余额","calculation_method":"sum","timestamp":"2026-08-07T15:00:00+08:00"}""",
        )

        requireNotNull(metric)
        assertEquals("CN_MARGIN:CN.SSE.MARGIN:20260807:1d:融资余额", metric.metricId)
        assertEquals("沪市融资余额", metric.metricName)
        assertEquals(1266993136806.0, metric.value, 0.0)
        assertEquals("20260807", metric.tradingDate)
        assertEquals("sum", metric.calculationMethod)
    }

    @Test
    fun rejectsMalformedMetricWithoutCrashingDataPage() {
        assertNull(decodeMarketMetric("{bad json"))
    }
}
