package com.marketmonitor.app.market

import com.marketmonitor.app.data.ImportedInstrument
import com.marketmonitor.app.data.ImportedMarketData
import com.marketmonitor.app.data.MarketCandle
import java.time.Instant
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class MarketOverviewTest {
    @Test
    fun missingMarketDataIsExplicitlyStaleAndEmpty() {
        val overview = MarketOverview.compute(null, now = Instant.parse("2026-08-06T00:00:00Z"))

        assertTrue(overview.stale)
        assertEquals(0, overview.instruments.size)
        assertTrue(overview.packageId == null)
    }

    @Test
    fun anomaliesAndCountsAreAggregatedPerInstrument() {
        val data = ImportedMarketData(
            packageId = "market-001",
            dataCutoff = "2026-08-05T15:00:00+08:00",
            instruments = listOf(
                ImportedInstrument(
                    instrumentId = "CN.SSE.STOCK.600519",
                    label = "600519 · SSE · STOCK",
                    candlesByPeriod = mapOf(
                        "1d" to listOf(
                            candle("PASS"),
                            candle("WARNING"),
                            candle("FAILED"),
                        ),
                    ),
                ),
            ),
        )

        val overview = MarketOverview.compute(data, now = Instant.parse("2026-08-06T00:00:00Z"))

        assertFalse(overview.stale)
        assertEquals(1, overview.anomalyCount)
        assertEquals(3, overview.totalCandles)
        assertEquals(QualityCounts(1, 1, 1), overview.instruments.single().quality)
    }

    @Test
    fun staleCutoffIsFlagged() {
        val data = ImportedMarketData(
            packageId = "market-old",
            dataCutoff = "2026-08-01T15:00:00+08:00",
            instruments = emptyList(),
        )

        val overview = MarketOverview.compute(data, now = Instant.parse("2026-08-06T00:00:00Z"))

        assertTrue(overview.stale)
    }

    private fun candle(status: String) = MarketCandle(
        openTimeSeconds = 1_752_600_000L,
        open = 100.0,
        high = 101.0,
        low = 99.0,
        close = 100.5,
        source = "test",
        qualityStatus = status,
    )
}
