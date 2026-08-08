package com.marketmonitor.app.trading

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class TradingStatsTest {
    private val calculator = PositionCalculator()
    private val stats = TradingStatsCalculator()

    @Test
    fun navReturnWinRateProfitFactorExposureHandComputed() {
        val result = calculator.calculate(
            trades = listOf(
                trade("t1", "X", TradeSide.BUY, 100, 10.0, dayMillis(1, 10)),
                trade("t2", "X", TradeSide.SELL, 100, 12.0, dayMillis(2, 10)),
                trade("t3", "Y", TradeSide.BUY, 100, 10.0, dayMillis(2, 11)),
                trade("t4", "Y", TradeSide.SELL, 100, 9.0, dayMillis(3, 10)),
                trade("t5", "X", TradeSide.BUY, 100, 10.0, dayMillis(3, 11)),
                trade("t6", "X", TradeSide.SELL, 100, 10.0, dayMillis(4, 10)),
            ),
            cashEvents = listOf(CashLedgerEvent("c1", CashKind.DEPOSIT, 10000.0, dayMillis(1, 9))),
        )
        val summary = stats.calculate(
            result,
            listOf(
                DailyClose(1, "X", 10.0),
                DailyClose(2, "X", 12.0),
                DailyClose(2, "Y", 10.0),
                DailyClose(3, "X", 10.0),
                DailyClose(3, "Y", 9.0),
                DailyClose(4, "X", 10.0),
            ),
        )

        // Day1: cash 9000 + X 1000 = 10000. Day2: cash 9000+1200-1000=9200 + Y 1000 = 10200.
        // Day3: cash 9200+900-1000=9100 + X 1000 = 10100. Day4: cash 9100+1000=10100.
        assertEquals(listOf(10000.0, 10200.0, 10100.0, 10100.0), summary.navCurve.map { it.nav })
        assertEquals(1.0, summary.totalReturnPct, 1e-9)
        val expectedDrawdown = (10200.0 - 10100.0) / 10200.0 * 100.0
        assertEquals(expectedDrawdown, summary.maxDrawdownPct, 1e-9)

        // Closed trades: +200 (t2), -100 (t4), 0 (t6). Win rate 1/3.
        assertEquals(100.0 / 3.0, summary.winRatePct, 1e-9)
        assertEquals(200.0, summary.grossProfit, 1e-9)
        assertEquals(100.0, summary.grossLoss, 1e-9)
        assertEquals(2.0, summary.profitFactor!!, 1e-9)

        // Exposure: day1 10%, day2 1000/10200, day3 1000/10100, day4 0%.
        assertEquals(10.0, summary.navCurve[0].exposurePct, 1e-9)
        assertEquals(0.0, summary.navCurve[3].exposurePct, 1e-9)
        assertTrue(summary.averageExposurePct > 0.0)
        assertEquals(10.0, summary.maxExposurePct, 1e-9)

        assertEquals(100.0, summary.realizedByStrategy[TradingStatsCalculator.UNASSIGNED]!!, 1e-9)
        assertEquals(200.0, summary.realizedByInstrument["X"]!!, 1e-9)
        assertEquals(-100.0, summary.realizedByInstrument["Y"]!!, 1e-9)
    }

    @Test
    fun drawdownWithHeldPositionIsMeasuredFromPeak() {
        val result = calculator.calculate(
            trades = listOf(trade("t1", "X", TradeSide.BUY, 100, 100.0, dayMillis(1, 10))),
            cashEvents = listOf(CashLedgerEvent("c1", CashKind.DEPOSIT, 10000.0, dayMillis(1, 9))),
        )
        val summary = stats.calculate(
            result,
            listOf(
                DailyClose(1, "X", 100.0),
                DailyClose(2, "X", 90.0),
                DailyClose(3, "X", 80.0),
                DailyClose(4, "X", 110.0),
            ),
        )
        assertEquals(listOf(10000.0, 9000.0, 8000.0, 11000.0), summary.navCurve.map { it.nav })
        assertEquals(20.0, summary.maxDrawdownPct, 1e-9)
        assertEquals(10.0, summary.totalReturnPct, 1e-9)
        assertEquals(100.0, summary.maxExposurePct, 1e-9)
        assertEquals(100.0, summary.navCurve[0].exposurePct, 1e-9)
    }

    @Test
    fun missingCloseFallsBackToCostAndIsFlagged() {
        val result = calculator.calculate(
            trades = listOf(trade("t1", "X", TradeSide.BUY, 100, 10.0, dayMillis(1, 10))),
            cashEvents = listOf(CashLedgerEvent("c1", CashKind.DEPOSIT, 10000.0, dayMillis(1, 9))),
        )
        val summary = stats.calculate(result, emptyList())
        assertTrue(summary.navCurve.all { it.markedWithFallback })
        assertEquals(1000.0, summary.navCurve.last().positionValue, 1e-9)
        assertEquals(10000.0, summary.navCurve.last().nav, 1e-9)
    }

    @Test
    fun attributionSplitsRealizedByStrategyAndInstrument() {
        val result = calculator.calculate(
            trades = listOf(
                trade("t1", "X", TradeSide.BUY, 100, 10.0, dayMillis(1, 10), strategy = "s1"),
                trade("t2", "X", TradeSide.SELL, 100, 12.0, dayMillis(2, 10), strategy = "s1"),
                trade("t3", "Y", TradeSide.BUY, 100, 10.0, dayMillis(2, 11), strategy = "s2"),
                trade("t4", "Y", TradeSide.SELL, 100, 9.0, dayMillis(3, 10), strategy = "s2"),
                trade("t5", "Z", TradeSide.BUY, 100, 10.0, dayMillis(3, 11), strategy = "s1"),
            ),
        )
        val summary = stats.calculate(
            result,
            listOf(
                DailyClose(2, "X", 12.0),
                DailyClose(3, "Y", 9.0),
                DailyClose(4, "Z", 12.0),
            ),
        )
        assertEquals(200.0, summary.realizedByStrategy["s1"]!!, 1e-9)
        assertEquals(-100.0, summary.realizedByStrategy["s2"]!!, 1e-9)
        assertEquals(200.0, summary.unrealizedByStrategy["s1"]!!, 1e-9)
        assertEquals(200.0, summary.unrealizedByInstrument["Z"]!!, 1e-9)
    }

    @Test
    fun profitFactorIsNullWhenThereAreNoLosses() {
        val result = calculator.calculate(
            trades = listOf(
                trade("t1", "X", TradeSide.BUY, 100, 10.0, dayMillis(1, 10)),
                trade("t2", "X", TradeSide.SELL, 100, 12.0, dayMillis(2, 10)),
            ),
        )
        val summary = stats.calculate(
            result,
            listOf(DailyClose(1, "X", 10.0), DailyClose(2, "X", 12.0)),
        )
        assertNull(summary.profitFactor)
        assertEquals(100.0, summary.winRatePct, 1e-9)
    }

    private fun trade(
        id: String,
        instrumentId: String,
        side: String,
        quantity: Long,
        price: Double,
        atMillis: Long,
        strategy: String? = null,
    ) = LedgerTrade(
        id = id,
        instrumentId = instrumentId,
        strategyId = strategy,
        side = side,
        quantity = quantity,
        price = price,
        executedAtEpochMillis = atMillis,
        createdAtEpochMillis = atMillis,
    )

    private fun dayMillis(day: Int, hour: Int): Long = (day.toLong() * 86_400_000L) + hour * 3_600_000L
}
