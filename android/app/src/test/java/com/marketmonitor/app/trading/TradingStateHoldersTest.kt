package com.marketmonitor.app.trading

import com.marketmonitor.app.trading.ui.TradeEntryDraft
import com.marketmonitor.app.trading.ui.TradeFilterState
import com.marketmonitor.app.trading.ui.draftFromTrade
import com.marketmonitor.app.trading.ui.parseEpochMillis
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TradingStateHoldersTest {
    @Test
    fun validDraftHasNoErrorsAndConvertsToInputValues() {
        val draft = TradeEntryDraft(
            instrumentId = "600519.SSE",
            side = TradeSide.BUY,
            quantity = "100",
            price = "10.5",
            executedAt = "2026-08-03T10:00:00+08:00",
            fees = "COMMISSION:5,STAMP_TAX:1.02",
        )
        assertTrue(draft.errors().isEmpty())
        assertEquals(100L, draft.quantity.toLong())
        assertEquals(10.5, draft.price.toDouble(), 0.0)
        assertEquals(2, draft.toFees().size)
        assertEquals(5.0, draft.toFees()[0].second, 0.0)
        assertTrue(draft.executedAtEpochMillis()!! > 0)
    }

    @Test
    fun invalidDraftReportsFieldErrors() {
        val draft = TradeEntryDraft(
            instrumentId = "",
            quantity = "0",
            price = "-1",
            executedAt = "not-a-time",
            fees = "badformat",
        )
        val errors = draft.errors()
        assertTrue(errors.any { it.contains("标的") })
        assertTrue(errors.any { it.contains("数量") })
        assertTrue(errors.any { it.contains("价格") })
        assertTrue(errors.any { it.contains("成交时间") })
        assertTrue(errors.any { it.contains("费用") })
    }

    @Test
    fun timestampParsingAcceptsIsoAndEpochMillis() {
        assertEquals(1_000_000L, parseEpochMillis("1000000"))
        assertTrue(parseEpochMillis("2026-08-03T10:00:00+08:00")!! > 0)
        assertEquals(null, parseEpochMillis("abc"))
    }

    @Test
    fun filterMatchesInstrumentStrategySideAndDayRange() {
        val trade = tradeView("t1", "600519.SSE", "s1", TradeSide.BUY, dayMillis(2, 10))
        assertTrue(TradeFilterState().matches(trade))
        assertTrue(TradeFilterState(instrument = "600519").matches(trade))
        assertFalse(TradeFilterState(instrument = "000001").matches(trade))
        assertTrue(TradeFilterState(strategy = "S1").matches(trade))
        assertFalse(TradeFilterState(strategy = "s2").matches(trade))
        assertTrue(TradeFilterState(side = TradeSide.BUY).matches(trade))
        assertFalse(TradeFilterState(side = TradeSide.SELL).matches(trade))
        assertTrue(TradeFilterState(fromEpochDay = 2, toEpochDay = 2).matches(trade))
        assertFalse(TradeFilterState(fromEpochDay = 3).matches(trade))
        assertFalse(TradeFilterState(toEpochDay = 1).matches(trade))
    }

    @Test
    fun draftFromTradePrefillsRevisionFields() {
        val view = tradeView("t1", "600519.SSE", "s1", TradeSide.BUY, dayMillis(2, 10), price = 10.5, quantity = 100)
        val draft = draftFromTrade(view)
        assertEquals("600519.SSE", draft.instrumentId)
        assertEquals("s1", draft.strategyId)
        assertEquals("100", draft.quantity)
        assertEquals("10.5", draft.price)
        assertTrue(draft.errors().isEmpty())
    }

    private fun tradeView(
        id: String,
        instrumentId: String,
        strategyId: String?,
        side: String,
        atMillis: Long,
        quantity: Long = 100,
        price: Double = 10.0,
    ) = TradeView(
        trade = TradeEntity(
            id = id,
            instrumentId = instrumentId,
            strategyId = strategyId,
            side = side,
            quantity = quantity,
            price = price,
            executedAtEpochMillis = atMillis,
            createdAtEpochMillis = atMillis,
            updatedAtEpochMillis = atMillis,
        ),
        fees = emptyList(),
    )

    private fun dayMillis(day: Int, hour: Int): Long = (day.toLong() * 86_400_000L) + hour * 3_600_000L
}
