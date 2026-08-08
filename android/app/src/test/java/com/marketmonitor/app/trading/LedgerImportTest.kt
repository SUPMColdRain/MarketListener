package com.marketmonitor.app.trading

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class LedgerImportTest {
    private val parser = LedgerImportParser()

    @Test
    fun fixedFixtureParsesIntoLedgerRows() {
        val content = fixture()
        val parsed = parser.parse(content, nowEpochMillis = 1_000_000L)
        assertEquals("2026-08-01 券商对账单", parsed.sourceLabel)
        assertEquals(1, parsed.strategies.size)
        assertEquals("strat-a", parsed.strategies[0].id)
        assertEquals(2, parsed.trades.size)
        assertEquals(2, parsed.fees.size)
        assertEquals(2, parsed.cashEvents.size)

        val first = parsed.trades[0]
        assertEquals("600519.SSE", first.instrumentId)
        assertEquals(TradeSide.BUY, first.side)
        assertEquals(300L, first.quantity)
        assertEquals(10.0, first.price, 1e-9)
        assertEquals("order-1", first.orderGroupId)
        assertEquals("strat-a", first.strategyId)
        assertEquals(5.0, parsed.fees.first { it.tradeId == first.id }.amount, 1e-9)
        assertTrue(parsed.cashEvents.any { it.kind == CashKind.DEPOSIT && it.amount == 10000.0 })
        assertTrue(parsed.cashEvents.any { it.kind == CashKind.WITHDRAWAL && it.amount == -2000.0 })
    }

    @Test
    fun checksumIsDeterministicAndIdentifiesDuplicateContent() {
        val content = fixture()
        val checksumA = parser.sha256(content.toByteArray(Charsets.UTF_8))
        val checksumB = parser.sha256(content.toByteArray(Charsets.UTF_8))
        assertEquals(64, checksumA.length)
        assertEquals(checksumA, checksumB)
        assertTrue(checksumA != parser.sha256("different".toByteArray(Charsets.UTF_8)))
    }

    @Test
    fun invalidLinesAreRejectedWithLineNumbers() {
        assertThrows(LedgerImportException::class.java) {
            parser.parse("", 0L)
        }
        assertThrows(LedgerImportException::class.java) {
            parser.parse("{\"type\":\"trade\"}", 0L)
        }
        assertThrows(LedgerImportException::class.java) {
            parser.parse(
                "{\"type\":\"header\",\"source_label\":\"x\"}\n" +
                    "{\"type\":\"trade\",\"instrument_id\":\"600519.SSE\",\"side\":\"HOLD\",\"quantity\":1,\"price\":1,\"executed_at\":1}",
                0L,
            )
        }
        assertThrows(LedgerImportException::class.java) {
            parser.parse(
                "{\"type\":\"header\",\"source_label\":\"x\"}\n" +
                    "{\"type\":\"trade\",\"instrument_id\":\"600519.SSE\",\"side\":\"BUY\",\"quantity\":-1,\"price\":1,\"executed_at\":1}",
                0L,
            )
        }
        assertThrows(LedgerImportException::class.java) {
            parser.parse(
                "{\"type\":\"header\",\"source_label\":\"x\"}\n" +
                    "{\"type\":\"trade\",\"instrument_id\":\"600519.SSE\",\"side\":\"BUY\",\"quantity\":1,\"price\":1,\"executed_at\":1,\"fees\":[{\"kind\":\"COMMISSION\",\"amount\":-1}]}",
                0L,
            )
        }
        val message = assertThrows(LedgerImportException::class.java) {
            parser.parse(
                "{\"type\":\"header\",\"source_label\":\"x\"}\n" +
                    "not-json",
                0L,
            )
        }
        assertTrue(message.message.orEmpty().contains("第 2 行"))
    }

    private fun fixture(): String = javaClass.classLoader
        ?.getResourceAsStream("ledger/sample-import.jsonl")
        ?.bufferedReader()
        ?.use { it.readText() }
        ?: error("Missing fixture ledger/sample-import.jsonl")
}
