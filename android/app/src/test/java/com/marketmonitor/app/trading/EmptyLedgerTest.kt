package com.marketmonitor.app.trading

import org.junit.Assert.assertEquals
import org.junit.Test

class EmptyLedgerTest {
    @Test
    fun emptyLedgerProducesDefaultSnapshotWithoutCrashing() {
        val result = PositionCalculator().calculate(emptyList())

        assertEquals(0L, result.finalSnapshot.epochDay)
        assertEquals(0.0, result.finalSnapshot.cash, 0.0)
        assertEquals(emptyMap<String, OpenPosition>(), result.finalSnapshot.positions)
    }
}
