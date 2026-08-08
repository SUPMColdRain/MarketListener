package com.marketmonitor.app.trading

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class PersonalBackupTest {
    private val codec = PersonalBackupCodec(iterations = 5_000)

    private val payload = BackupPayload(
        formatVersion = BACKUP_FORMAT_VERSION,
        appVersion = "0.1.0",
        exportedAtIso = "2026-08-06T00:00:00+08:00",
        tables = mapOf(
            "strategies" to listOf(mapOf("id" to "s1", "name" to "均线回踩", "description" to null, "createdAtEpochMillis" to 1L)),
            "ledger_imports" to emptyList(),
            "trades" to listOf(
                mapOf(
                    "id" to "t1",
                    "instrumentId" to "600519.SSE",
                    "strategyId" to "s1",
                    "side" to "BUY",
                    "quantity" to 100L,
                    "price" to 10.0,
                    "executedAtEpochMillis" to 2L,
                    "status" to "EXECUTED",
                    "parentTradeId" to null,
                    "orderGroupId" to null,
                    "importBatchId" to null,
                    "note" to null,
                    "createdAtEpochMillis" to 3L,
                    "updatedAtEpochMillis" to 3L,
                ),
            ),
            "trade_fees" to listOf(mapOf("id" to "f1", "tradeId" to "t1", "kind" to "COMMISSION", "amount" to 5.0, "note" to null)),
            "cash_events" to emptyList(),
            "split_events" to emptyList(),
            "position_snapshots" to emptyList(),
            "watchlist" to emptyList(),
        ),
    )

    @Test
    fun exportImportRoundTripPreservesAllTables() {
        val encrypted = codec.export("correct horse battery".toCharArray(), payload)
        val restored = codec.import("correct horse battery".toCharArray(), encrypted)
        assertEquals(payload.tables, restored.tables)
        assertEquals(payload.appVersion, restored.appVersion)
        assertEquals(1, restored.formatVersion)
    }

    @Test
    fun wrongPasswordFailsWithoutReturningData() {
        val encrypted = codec.export("correct password".toCharArray(), payload)
        assertThrows(BackupException.WrongPassword::class.java) {
            codec.import("wrong password".toCharArray(), encrypted)
        }
    }

    @Test
    fun tamperedCiphertextFailsAuthentication() {
        val encrypted = codec.export("password".toCharArray(), payload)
        val tampered = encrypted.copyOf()
        tampered[tampered.size - 1] = (tampered.last().toInt() xor 0x01).toByte()
        assertThrows(BackupException.WrongPassword::class.java) {
            codec.import("password".toCharArray(), tampered)
        }
    }

    @Test
    fun truncatedFileIsRejected() {
        val encrypted = codec.export("password".toCharArray(), payload)
        val truncated = encrypted.copyOf(20)
        assertThrows(BackupException.Truncated::class.java) {
            codec.import("password".toCharArray(), truncated)
        }
    }

    @Test
    fun unknownMagicIsRejected() {
        val encrypted = codec.export("password".toCharArray(), payload)
        val badMagic = encrypted.copyOf()
        badMagic[0] = 'X'.code.toByte()
        assertThrows(BackupException.InvalidFormat::class.java) {
            codec.import("password".toCharArray(), badMagic)
        }
    }

    @Test
    fun unsupportedVersionIsRejected() {
        val encrypted = codec.export("password".toCharArray(), payload)
        val badVersion = encrypted.copyOf()
        badVersion[5] = 9
        assertThrows(BackupException.UnsupportedVersion::class.java) {
            codec.import("password".toCharArray(), badVersion)
        }
    }

    @Test
    fun restorePlannerOrdersChildrenBeforeParentsAndRejectsUnknownTables() {
        val plan = RestorePlanner().plan(payload)
        assertEquals(
            listOf("trade_fees", "trades", "cash_events", "split_events", "position_snapshots", "ledger_imports", "strategies", "watchlist"),
            plan.deleteOrder,
        )
        assertEquals(
            listOf("strategies", "ledger_imports", "trades", "trade_fees", "cash_events", "split_events", "position_snapshots", "watchlist"),
            plan.insertOrder.map { it.table },
        )

        val unknown = payload.copy(tables = payload.tables + ("hacker_table" to emptyList()))
        assertThrows(BackupException.CorruptPayload::class.java) { RestorePlanner().plan(unknown) }

        val badColumn = payload.copy(
            tables = payload.tables + ("strategies" to listOf(mapOf("id" to "s1", "evil" to 1))),
        )
        assertThrows(BackupException.CorruptPayload::class.java) { RestorePlanner().plan(badColumn) }
    }

    @Test
    fun corruptJsonPayloadIsRejected() {
        // Valid GCM but structurally corrupt payload: a row value that is not a scalar.
        val bad = payload.copy(
            tables = payload.tables + ("watchlist" to listOf(mapOf("instrumentId" to mapOf("bad" to true), "createdAt" to "x"))),
        )
        val encrypted = codec.export("password".toCharArray(), bad)
        assertThrows(BackupException.CorruptPayload::class.java) {
            codec.import("password".toCharArray(), encrypted)
        }
    }
}
