package com.marketmonitor.app.ui.market

import com.marketmonitor.app.data.ImportedInstrument
import com.marketmonitor.app.data.MarketCandle
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class QuoteRowMapperTest {

    @Test
    fun latestPriceAndChangePctComeFromRealCandles() {
        val row = quoteRowFor(
            instrument(
                id = "CN.SSE.STOCK.600519",
                label = "600519 · SSE · STOCK",
                candles = listOf(
                    candle(1L, close = 100.0),
                    candle(2L, close = 103.5),
                ),
            ),
        )

        assertEquals(103.5, row.latestPrice!!, 1e-9)
        assertEquals(3.5, row.changePct!!, 1e-9)
        assertEquals("1d", row.period)
        assertEquals("600519", row.code)
        assertEquals(2, row.sparklinePoints.size)
    }

    @Test
    fun missingPreviousCloseLeavesPctNullButKeepsPrice() {
        val row = quoteRowFor(
            instrument(
                id = "HK.HKEX.STOCK.00700",
                label = "00700 · HKEX · STOCK",
                candles = listOf(candle(1L, close = 320.0)),
            ),
        )

        assertEquals(320.0, row.latestPrice!!, 1e-9)
        assertEquals("00700", row.code)
        assertNull(row.changePct)
        assertEquals(1, row.sparklinePoints.size)
    }

    @Test
    fun noCandlesYieldsNullQuoteAndEmptySparkline() {
        val row = quoteRowFor(
            instrument(
                id = "CN.SHFE.FUTURE.AU",
                label = "AU · SHFE · FUTURE",
                candles = emptyList(),
            ),
        )

        assertEquals("AU", row.code)
        assertNull(row.latestPrice)
        assertNull(row.changePct)
        assertTrue(row.sparklinePoints.isEmpty())
    }

    @Test
    fun nonFiniteValuesAreExcludedAndNeverBecomeZero() {
        val row = quoteRowFor(
            instrument(
                id = "CN.SSE.STOCK.600519",
                candles = listOf(
                    candle(1L, close = Double.NaN),
                    candle(2L, close = 10.0),
                    candle(3L, close = Double.POSITIVE_INFINITY),
                ),
            ),
        )

        assertEquals(10.0, row.latestPrice!!, 1e-9)
        assertNull(row.changePct)
        assertEquals(listOf(10.0), row.sparklinePoints.map { it.value })
    }

    @Test
    fun sparklineUsesOpenTimeMillisAndCloses() {
        val row = quoteRowFor(
            instrument(
                id = "CN.SSE.STOCK.600519",
                candles = listOf(
                    candle(1_700_000_000L, close = 9.5),
                    candle(1_700_086_400L, close = 10.0),
                ),
            ),
        )

        assertEquals(1_700_000_000_000L, row.sparklinePoints[0].epochMillis)
        assertEquals(10.0, row.sparklinePoints[1].value, 1e-9)
    }

    @Test
    fun priceFormattingStripsPaddingAndIsLocaleStable() {
        assertEquals("1520.21", formatQuotePrice(1520.210))
        assertEquals("780.42", formatQuotePrice(780.42))
        assertEquals("12.5", formatQuotePrice(12.500))
    }

    @Test
    fun changePctFormattingNeverShowsNegativeZero() {
        assertEquals("+3.50%", formatQuoteChangePct(3.5))
        assertEquals("-2.31%", formatQuoteChangePct(-2.31))
        assertEquals("+0.00%", formatQuoteChangePct(-0.004))
    }

    @Test
    fun labelWithoutSeparatorFallsBackToInstrumentIdAsCode() {
        val row = quoteRowFor(
            instrument(
                id = "custom-key",
                label = "自定义名称",
                candles = listOf(candle(1L, close = 1.0)),
            ),
        )

        assertEquals("custom-key", row.code)
    }

    private fun instrument(
        id: String,
        candles: List<MarketCandle>,
        label: String? = null,
    ) = ImportedInstrument(
        instrumentId = id,
        label = label ?: "$id · TEST · STOCK",
        candlesByPeriod = mapOf("1d" to candles),
    )

    private fun candle(openTimeSeconds: Long, close: Double) = MarketCandle(
        openTimeSeconds = openTimeSeconds,
        open = close,
        high = close,
        low = close,
        close = close,
        source = "test",
        qualityStatus = "PASS",
    )
}
