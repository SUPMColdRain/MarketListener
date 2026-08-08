package com.marketmonitor.app.trading

import java.sql.Connection
import java.sql.DriverManager
import java.sql.SQLException
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

/**
 * Executes the exact migration SQL used by UserDatabase v1→v2 against real
 * SQLite, proving table/column/index/FK/CHECK structure and transactional
 * rollback for restore.
 */
class TradingSchemaMigrationTest {
    @Test
    fun migrationCreatesTradingTablesAndPreservesWatchlist() {
        connection().use { connection ->
            connection.createStatement().use { statement ->
                statement.execute(
                    "CREATE TABLE watchlist (instrumentId TEXT NOT NULL, createdAt TEXT NOT NULL, " +
                        "PRIMARY KEY(instrumentId))",
                )
                statement.execute("INSERT INTO watchlist VALUES ('600519.SSE', '2026-08-01T00:00:00+08:00')")
                TradingSchema.SQL_1_2.forEach(statement::execute)
            }

            val tables = connection.createStatement().use { statement ->
                statement.executeQuery("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").use { cursor ->
                    buildList {
                        while (cursor.next()) add(cursor.getString(1))
                    }
                }
            }
            setOf(
                "watchlist",
                "strategies",
                "ledger_imports",
                "trades",
                "trade_fees",
                "cash_events",
                "split_events",
                "position_snapshots",
            ).forEach { assertTrue("missing table $it", it in tables) }

            val watchlist = connection.createStatement().use { statement ->
                statement.executeQuery("SELECT instrumentId FROM watchlist").use { cursor ->
                    if (cursor.next()) cursor.getString(1) else null
                }
            }
            assertEquals("600519.SSE", watchlist)
        }
    }

    @Test
    fun tradeTableHasExpectedColumnsForeignKeysAndIndices() {
        connection().use { connection ->
            TradingSchema.SQL_1_2.forEach { sql -> connection.createStatement().use { it.execute(sql) } }
            val columns = connection.createStatement().use { statement ->
                statement.executeQuery("PRAGMA table_info(trades)").use { cursor ->
                    buildList {
                        while (cursor.next()) add(cursor.getString(2) to cursor.getString(3))
                    }
                }
            }
            assertEquals(
                listOf(
                    "id" to "TEXT",
                    "instrumentId" to "TEXT",
                    "strategyId" to "TEXT",
                    "side" to "TEXT",
                    "quantity" to "INTEGER",
                    "price" to "REAL",
                    "executedAtEpochMillis" to "INTEGER",
                    "status" to "TEXT",
                    "parentTradeId" to "TEXT",
                    "orderGroupId" to "TEXT",
                    "importBatchId" to "TEXT",
                    "note" to "TEXT",
                    "createdAtEpochMillis" to "INTEGER",
                    "updatedAtEpochMillis" to "INTEGER",
                ),
                columns,
            )

            val foreignKeys = connection.createStatement().use { statement ->
                statement.executeQuery("PRAGMA foreign_key_list(trades)").use { cursor ->
                    buildList {
                        while (cursor.next()) add(cursor.getString(3) to cursor.getString(4))
                    }
                }
            }
            assertTrue(foreignKeys.contains("strategies" to "strategyId"))
            assertTrue(foreignKeys.contains("ledger_imports" to "importBatchId"))

            val indices = connection.createStatement().use { statement ->
                statement.executeQuery("PRAGMA index_list(trades)").use { cursor ->
                    buildList {
                        while (cursor.next()) add(cursor.getString(2))
                    }
                }
            }
            assertTrue(indices.contains("index_trades_instrument_time"))
            assertTrue(indices.contains("index_trades_strategy"))
            assertTrue(indices.contains("index_trades_import_batch"))
        }
    }

    @Test
    fun checkConstraintsRejectInvalidLedgerRows() {
        connection().use { connection ->
            TradingSchema.SQL_1_2.forEach { sql -> connection.createStatement().use { it.execute(sql) } }
            val statement = connection.createStatement()
            assertFails { statement.execute("INSERT INTO trades (id, instrumentId, side, quantity, price, executedAtEpochMillis, status, createdAtEpochMillis, updatedAtEpochMillis) VALUES ('t1','600519.SSE','HOLD',100,10,0,'EXECUTED',0,0)") }
            assertFails { statement.execute("INSERT INTO trades (id, instrumentId, side, quantity, price, executedAtEpochMillis, status, createdAtEpochMillis, updatedAtEpochMillis) VALUES ('t2','600519.SSE','BUY',0,10,0,'EXECUTED',0,0)") }
            assertFails { statement.execute("INSERT INTO trades (id, instrumentId, side, quantity, price, executedAtEpochMillis, status, createdAtEpochMillis, updatedAtEpochMillis) VALUES ('t3','600519.SSE','BUY',100,-1,0,'EXECUTED',0,0)") }
            assertFails { statement.execute("INSERT INTO cash_events (id, kind, amount, occurredAtEpochMillis) VALUES ('c1','DEPOSIT',0,0)") }
            assertFails { statement.execute("INSERT INTO split_events (id, instrumentId, exDateEpochDay, newPerOld) VALUES ('s1','600519.SSE',0,-1)") }
        }
    }

    @Test
    fun interruptedRestoreRollsBackToOriginalLedger() {
        connection().use { connection ->
            connection.createStatement().use { statement ->
                statement.execute("PRAGMA foreign_keys = ON")
                TradingSchema.SQL_1_2.forEach(statement::execute)
                statement.execute(
                    "INSERT INTO strategies (id, name, createdAtEpochMillis) VALUES ('strat-a', '均线回踩', 0)",
                )
                statement.execute(
                    "INSERT INTO trades (id, instrumentId, strategyId, side, quantity, price, executedAtEpochMillis, " +
                        "status, createdAtEpochMillis, updatedAtEpochMillis) " +
                        "VALUES ('t1','600519.SSE','strat-a','BUY',100,10.0,0,'EXECUTED',0,0)",
                )
                statement.execute(
                    "INSERT INTO trade_fees (id, tradeId, kind, amount) VALUES ('f1','t1','COMMISSION',5.0)",
                )
            }

            connection.autoCommit = false
            try {
                connection.createStatement().use { statement ->
                    RestorePlanner.DELETE_ORDER.forEach { table ->
                        statement.execute("DELETE FROM $table")
                    }
                    statement.execute(
                        "INSERT INTO strategies (id, name, createdAtEpochMillis) VALUES ('strat-new', '新策略', 1)",
                    )
                    statement.execute(
                        "INSERT INTO trades (id, instrumentId, strategyId, side, quantity, price, executedAtEpochMillis, " +
                            "status, createdAtEpochMillis, updatedAtEpochMillis) " +
                            "VALUES ('t-new','600519.SSE','strat-new','BUY',50,9.0,0,'EXECUTED',0,0)",
                    )
                    // Poisoned insert: fee references a trade that does not exist.
                    statement.execute(
                        "INSERT INTO trade_fees (id, tradeId, kind, amount) VALUES ('f-bad','t-missing','COMMISSION',1.0)",
                    )
                }
                fail("expected FK violation")
            } catch (_: SQLException) {
                connection.rollback()
            } finally {
                connection.autoCommit = true
            }

            val tradeCount = connection.createStatement().use { statement ->
                statement.executeQuery("SELECT count(*) FROM trades").use { cursor ->
                    cursor.next()
                    cursor.getLong(1)
                }
            }
            val feeCount = connection.createStatement().use { statement ->
                statement.executeQuery("SELECT count(*) FROM trade_fees").use { cursor ->
                    cursor.next()
                    cursor.getLong(1)
                }
            }
            assertEquals(1L, tradeCount)
            assertEquals(1L, feeCount)
            val originalTrade = connection.createStatement().use { statement ->
                statement.executeQuery("SELECT instrumentId FROM trades WHERE id='t1'").use { cursor ->
                    if (cursor.next()) cursor.getString(1) else null
                }
            }
            assertEquals("600519.SSE", originalTrade)
        }
    }

    private fun assertFails(block: () -> Unit) {
        try {
            block()
            fail("expected SQLException")
        } catch (_: SQLException) {
            // expected
        }
    }

    private fun connection(): Connection = DriverManager.getConnection("jdbc:sqlite::memory:")
}
