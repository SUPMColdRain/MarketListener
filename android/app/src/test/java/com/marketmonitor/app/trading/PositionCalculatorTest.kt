package com.marketmonitor.app.trading

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class PositionCalculatorTest {
    private val calculator = PositionCalculator()

    @Test
    fun partialFillsUseWeightedAverageCost() {
        val result = calculator.calculate(
            trades = listOf(
                trade("t1", "600519.SSE", TradeSide.BUY, 300, 10.0, dayMillis(1, 10)),
                trade("t2", "600519.SSE", TradeSide.BUY, 200, 12.0, dayMillis(1, 11)),
            ),
        )
        val position = result.finalSnapshot.positions.getValue("600519.SSE")
        assertEquals(500L, position.quantity)
        assertEquals(5400.0, position.costBasis, 1e-9)
        assertEquals(10.8, position.averageCost, 1e-9)
        assertEquals(-5400.0, result.finalSnapshot.cash, 1e-9)
    }

    @Test
    fun buyAndSellWithFeesRealizesExpectedPnl() {
        val result = calculator.calculate(
            trades = listOf(
                trade("t1", "600519.SSE", TradeSide.BUY, 100, 10.0, dayMillis(1, 10), fees = listOf(LedgerFee("COMMISSION", 5.0))),
                trade("t2", "600519.SSE", TradeSide.SELL, 100, 12.0, dayMillis(2, 10), fees = listOf(LedgerFee("STAMP_TAX", 3.0))),
            ),
        )
        assertEquals(192.0, result.closedTradePnl.getValue("t2"), 1e-9)
        assertEquals(0L, result.finalSnapshot.positions["600519.SSE"]?.quantity ?: -1L)
        assertEquals(192.0, result.finalSnapshot.cash, 1e-9)
        assertEquals(8.0, result.totalFees, 1e-9)
        assertEquals(192.0, result.finalSnapshot.realizedPnlTotal, 1e-9)
    }

    @Test
    fun splitAdjustsQuantityAndKeepsCostBasis() {
        val result = calculator.calculate(
            trades = listOf(trade("t1", "600519.SSE", TradeSide.BUY, 1000, 10.0, dayMillis(1, 10))),
            splits = listOf(SplitLedgerEvent("s1", "600519.SSE", epochDayOf(dayMillis(2, 0)), 10.0)),
        )
        val position = result.finalSnapshot.positions.getValue("600519.SSE")
        assertEquals(10000L, position.quantity)
        assertEquals(10000.0, position.costBasis, 1e-9)
        assertEquals(1.0, position.averageCost, 1e-9)
        assertEquals(2, result.snapshots.size)
        assertEquals(1000L, result.snapshots[0].positions.getValue("600519.SSE").quantity)
        assertEquals(10000L, result.snapshots[1].positions.getValue("600519.SSE").quantity)
    }

    @Test
    fun cancelledAndRevisedTradesAreIgnored() {
        val result = calculator.calculate(
            trades = listOf(
                trade("t1", "600519.SSE", TradeSide.BUY, 100, 10.0, dayMillis(1, 10), status = TradeStatus.CANCELLED),
                trade("t2", "600519.SSE", TradeSide.BUY, 100, 10.0, dayMillis(1, 11), status = TradeStatus.REVISED),
                trade("t3", "600519.SSE", TradeSide.BUY, 100, 12.0, dayMillis(1, 12), parent = "t2"),
            ),
        )
        val position = result.finalSnapshot.positions.getValue("600519.SSE")
        assertEquals(100L, position.quantity)
        assertEquals(1200.0, position.costBasis, 1e-9)
        assertEquals(listOf("t3"), result.executedTrades.map { it.id })
    }

    @Test
    fun cashEventsMoveOnlyTheCashLeg() {
        val result = calculator.calculate(
            trades = listOf(trade("t1", "600519.SSE", TradeSide.BUY, 100, 10.0, dayMillis(1, 10))),
            cashEvents = listOf(
                CashLedgerEvent("c1", CashKind.DEPOSIT, 10000.0, dayMillis(1, 9)),
                CashLedgerEvent("c2", CashKind.WITHDRAWAL, -2000.0, dayMillis(2, 10)),
            ),
        )
        assertEquals(7000.0, result.finalSnapshot.cash, 1e-9)
        assertEquals(100L, result.finalSnapshot.positions.getValue("600519.SSE").quantity)
    }

    @Test
    fun sellExceedingPositionIsRejected() {
        assertThrows(PositionException::class.java) {
            calculator.calculate(
                trades = listOf(trade("t1", "600519.SSE", TradeSide.SELL, 100, 10.0, dayMillis(1, 10))),
            )
        }
    }

    @Test
    fun sellMoreThanHeldIsRejected() {
        assertThrows(PositionException::class.java) {
            calculator.calculate(
                trades = listOf(
                    trade("t1", "600519.SSE", TradeSide.BUY, 100, 10.0, dayMillis(1, 10)),
                    trade("t2", "600519.SSE", TradeSide.SELL, 101, 10.0, dayMillis(2, 10)),
                ),
            )
        }
    }

    private fun trade(
        id: String,
        instrumentId: String,
        side: String,
        quantity: Long,
        price: Double,
        atMillis: Long,
        status: String = TradeStatus.EXECUTED,
        parent: String? = null,
        fees: List<LedgerFee> = emptyList(),
    ) = LedgerTrade(
        id = id,
        instrumentId = instrumentId,
        side = side,
        quantity = quantity,
        price = price,
        executedAtEpochMillis = atMillis,
        status = status,
        parentTradeId = parent,
        createdAtEpochMillis = atMillis,
        fees = fees,
    )

    private fun dayMillis(day: Int, hour: Int): Long = (day.toLong() * 86_400_000L) + hour * 3_600_000L
}
