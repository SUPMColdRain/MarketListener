package com.marketmonitor.app.trading

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import com.marketmonitor.app.data.WatchlistEntity

/** Side of a trade fill. Only long-side A-share trading is modeled. */
object TradeSide {
    const val BUY = "BUY"
    const val SELL = "SELL"
}

/** Lifecycle status of a trade row. Revisions mark the parent as REVISED. */
object TradeStatus {
    const val EXECUTED = "EXECUTED"
    const val REVISED = "REVISED"
    const val CANCELLED = "CANCELLED"
}

/** Cash event kinds stored with signed amounts (deposits positive, withdrawals negative). */
object CashKind {
    const val DEPOSIT = "DEPOSIT"
    const val WITHDRAWAL = "WITHDRAWAL"
    const val DIVIDEND = "DIVIDEND"
    const val TAX_REFUND = "TAX_REFUND"
    const val OTHER = "OTHER"
}

/** Fee kinds attached to a trade. */
object FeeKind {
    const val COMMISSION = "COMMISSION"
    const val STAMP_TAX = "STAMP_TAX"
    const val TRANSFER_FEE = "TRANSFER_FEE"
    const val OTHER = "OTHER"
}

@Entity(tableName = "strategies")
data class StrategyEntity(
    @PrimaryKey val id: String,
    val name: String,
    val description: String? = null,
    val createdAtEpochMillis: Long,
)

@Entity(
    tableName = "ledger_imports",
    indices = [Index(value = ["checksum"], name = "index_ledger_imports_checksum", unique = true)],
)
data class LedgerImportEntity(
    @PrimaryKey val id: String,
    val checksum: String,
    val sourceLabel: String,
    val importedAtEpochMillis: Long,
    val tradeCount: Int,
    val cashCount: Int,
)

@Entity(
    tableName = "trades",
    foreignKeys = [
        ForeignKey(
            entity = StrategyEntity::class,
            parentColumns = ["id"],
            childColumns = ["strategyId"],
            onDelete = ForeignKey.SET_NULL,
        ),
        ForeignKey(
            entity = LedgerImportEntity::class,
            parentColumns = ["id"],
            childColumns = ["importBatchId"],
            onDelete = ForeignKey.RESTRICT,
        ),
    ],
    indices = [
        Index(value = ["instrumentId", "executedAtEpochMillis"], name = "index_trades_instrument_time"),
        Index(value = ["strategyId"], name = "index_trades_strategy"),
        Index(value = ["importBatchId"], name = "index_trades_import_batch"),
    ],
)
data class TradeEntity(
    @PrimaryKey val id: String,
    val instrumentId: String,
    val strategyId: String? = null,
    val side: String,
    val quantity: Long,
    val price: Double,
    val executedAtEpochMillis: Long,
    val status: String = TradeStatus.EXECUTED,
    val parentTradeId: String? = null,
    val orderGroupId: String? = null,
    val importBatchId: String? = null,
    val note: String? = null,
    val createdAtEpochMillis: Long,
    val updatedAtEpochMillis: Long,
)

@Entity(
    tableName = "trade_fees",
    foreignKeys = [
        ForeignKey(
            entity = TradeEntity::class,
            parentColumns = ["id"],
            childColumns = ["tradeId"],
            onDelete = ForeignKey.CASCADE,
        ),
    ],
    indices = [Index(value = ["tradeId"], name = "index_trade_fees_trade_id")],
)
data class FeeEntity(
    @PrimaryKey val id: String,
    val tradeId: String,
    val kind: String,
    val amount: Double,
    val note: String? = null,
)

@Entity(
    tableName = "cash_events",
    indices = [Index(value = ["occurredAtEpochMillis"], name = "index_cash_events_occurred_at")],
)
data class CashEventEntity(
    @PrimaryKey val id: String,
    val kind: String,
    val amount: Double,
    val occurredAtEpochMillis: Long,
    val importBatchId: String? = null,
    val note: String? = null,
)

/** Split (送转/拆股) with newPerOld shares per old share, applied from exDateEpochDay onward. */
@Entity(
    tableName = "split_events",
    indices = [Index(value = ["instrumentId", "exDateEpochDay"], name = "index_split_events_instrument_day")],
)
data class SplitEventEntity(
    @PrimaryKey val id: String,
    val instrumentId: String,
    val exDateEpochDay: Long,
    val newPerOld: Double,
)

@Entity(
    tableName = "position_snapshots",
    primaryKeys = ["epochDay", "instrumentId"],
)
data class PositionSnapshotEntity(
    val epochDay: Long,
    val instrumentId: String,
    val quantity: Long,
    val costBasis: Double,
    val realizedPnl: Double,
    val updatedAtEpochMillis: Long,
)

@Dao
interface TradingDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertStrategy(strategy: StrategyEntity)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertStrategies(strategies: List<StrategyEntity>)

    @Query("SELECT * FROM strategies ORDER BY name")
    suspend fun strategies(): List<StrategyEntity>

    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertTrade(trade: TradeEntity)

    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertTrades(trades: List<TradeEntity>)

    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertFees(fees: List<FeeEntity>)

    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertCash(cash: CashEventEntity)

    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertCashAll(cash: List<CashEventEntity>)

    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertSplits(splits: List<SplitEventEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertPositionSnapshots(snapshots: List<PositionSnapshotEntity>)

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insertLedgerImport(ledgerImport: LedgerImportEntity): Long

    @Query("SELECT * FROM ledger_imports WHERE checksum = :checksum LIMIT 1")
    suspend fun importByChecksum(checksum: String): LedgerImportEntity?

    @Query("UPDATE trades SET status = :status, updatedAtEpochMillis = :updatedAt WHERE id = :tradeId")
    suspend fun updateTradeStatus(tradeId: String, status: String, updatedAt: Long)

    @Query("SELECT * FROM trades ORDER BY executedAtEpochMillis, createdAtEpochMillis, id")
    suspend fun tradesAll(): List<TradeEntity>

    @Query("SELECT * FROM trades WHERE instrumentId = :instrumentId ORDER BY executedAtEpochMillis")
    suspend fun tradesByInstrument(instrumentId: String): List<TradeEntity>

    @Query(
        "SELECT * FROM trades WHERE executedAtEpochMillis BETWEEN :fromEpochMillis AND :toEpochMillis " +
            "ORDER BY executedAtEpochMillis",
    )
    suspend fun tradesBetween(fromEpochMillis: Long, toEpochMillis: Long): List<TradeEntity>

    @Query("SELECT * FROM trades WHERE importBatchId = :importBatchId ORDER BY executedAtEpochMillis")
    suspend fun tradesByImport(importBatchId: String): List<TradeEntity>

    @Query("SELECT * FROM trades WHERE id = :tradeId LIMIT 1")
    suspend fun tradeById(tradeId: String): TradeEntity?

    @Query("SELECT * FROM trade_fees ORDER BY tradeId")
    suspend fun feesAll(): List<FeeEntity>

    @Query("SELECT * FROM trade_fees WHERE tradeId = :tradeId ORDER BY kind")
    suspend fun feesForTrade(tradeId: String): List<FeeEntity>

    @Query("SELECT * FROM cash_events ORDER BY occurredAtEpochMillis")
    suspend fun cashEvents(): List<CashEventEntity>

    @Query("SELECT * FROM split_events ORDER BY exDateEpochDay")
    suspend fun splits(): List<SplitEventEntity>

    @Query("SELECT * FROM position_snapshots WHERE epochDay BETWEEN :fromEpochDay AND :toEpochDay ORDER BY epochDay")
    suspend fun positionSnapshots(fromEpochDay: Long, toEpochDay: Long): List<PositionSnapshotEntity>

    @Query("SELECT * FROM position_snapshots ORDER BY epochDay, instrumentId")
    suspend fun positionSnapshotsAll(): List<PositionSnapshotEntity>

    @Query("SELECT * FROM ledger_imports ORDER BY importedAtEpochMillis")
    suspend fun ledgerImportsAll(): List<LedgerImportEntity>

    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertLedgerImportsAll(imports: List<LedgerImportEntity>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertWatchlistAll(watchlist: List<WatchlistEntity>)

    @Query("SELECT * FROM watchlist ORDER BY createdAt")
    suspend fun watchlistAll(): List<WatchlistEntity>

    // Restore helpers: children are cleared before parents so foreign keys stay valid.
    @Query("DELETE FROM trade_fees") suspend fun clearFees()
    @Query("DELETE FROM trades") suspend fun clearTrades()
    @Query("DELETE FROM cash_events") suspend fun clearCash()
    @Query("DELETE FROM split_events") suspend fun clearSplits()
    @Query("DELETE FROM position_snapshots") suspend fun clearPositions()
    @Query("DELETE FROM ledger_imports") suspend fun clearImports()
    @Query("DELETE FROM strategies") suspend fun clearStrategies()
    @Query("DELETE FROM watchlist") suspend fun clearWatchlist()
}

/**
 * Hand-written DDL shared by the v1→v2 migration and the SQL-level migration tests.
 * CHECK constraints are defense in depth; the domain layer validates the same rules.
 * Room's TableInfo comparison ignores CHECK constraints, so these tables are also
 * accepted by Room's runtime identity validation.
 */
object TradingSchema {
    val CREATE_STRATEGIES = """
        CREATE TABLE IF NOT EXISTS strategies (
            id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            createdAtEpochMillis INTEGER NOT NULL,
            PRIMARY KEY(id)
        )
    """.trimIndent()

    val CREATE_LEDGER_IMPORTS = """
        CREATE TABLE IF NOT EXISTS ledger_imports (
            id TEXT NOT NULL,
            checksum TEXT NOT NULL,
            sourceLabel TEXT NOT NULL,
            importedAtEpochMillis INTEGER NOT NULL,
            tradeCount INTEGER NOT NULL,
            cashCount INTEGER NOT NULL,
            PRIMARY KEY(id)
        )
    """.trimIndent()

    val CREATE_TRADES = """
        CREATE TABLE IF NOT EXISTS trades (
            id TEXT NOT NULL,
            instrumentId TEXT NOT NULL,
            strategyId TEXT,
            side TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            executedAtEpochMillis INTEGER NOT NULL,
            status TEXT NOT NULL,
            parentTradeId TEXT,
            orderGroupId TEXT,
            importBatchId TEXT,
            note TEXT,
            createdAtEpochMillis INTEGER NOT NULL,
            updatedAtEpochMillis INTEGER NOT NULL,
            PRIMARY KEY(id),
            FOREIGN KEY(strategyId) REFERENCES strategies(id) ON DELETE SET NULL,
            FOREIGN KEY(importBatchId) REFERENCES ledger_imports(id) ON DELETE RESTRICT,
            CHECK(side IN ('BUY', 'SELL')),
            CHECK(quantity > 0),
            CHECK(price >= 0),
            CHECK(status IN ('EXECUTED', 'REVISED', 'CANCELLED'))
        )
    """.trimIndent()

    val CREATE_TRADE_FEES = """
        CREATE TABLE IF NOT EXISTS trade_fees (
            id TEXT NOT NULL,
            tradeId TEXT NOT NULL,
            kind TEXT NOT NULL,
            amount REAL NOT NULL,
            note TEXT,
            PRIMARY KEY(id),
            FOREIGN KEY(tradeId) REFERENCES trades(id) ON DELETE CASCADE,
            CHECK(amount >= 0)
        )
    """.trimIndent()

    val CREATE_CASH_EVENTS = """
        CREATE TABLE IF NOT EXISTS cash_events (
            id TEXT NOT NULL,
            kind TEXT NOT NULL,
            amount REAL NOT NULL,
            occurredAtEpochMillis INTEGER NOT NULL,
            importBatchId TEXT,
            note TEXT,
            PRIMARY KEY(id),
            CHECK(kind IN ('DEPOSIT', 'WITHDRAWAL', 'DIVIDEND', 'TAX_REFUND', 'OTHER')),
            CHECK(amount != 0)
        )
    """.trimIndent()

    val CREATE_SPLIT_EVENTS = """
        CREATE TABLE IF NOT EXISTS split_events (
            id TEXT NOT NULL,
            instrumentId TEXT NOT NULL,
            exDateEpochDay INTEGER NOT NULL,
            newPerOld REAL NOT NULL,
            PRIMARY KEY(id),
            CHECK(newPerOld > 0)
        )
    """.trimIndent()

    val CREATE_POSITION_SNAPSHOTS = """
        CREATE TABLE IF NOT EXISTS position_snapshots (
            epochDay INTEGER NOT NULL,
            instrumentId TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            costBasis REAL NOT NULL,
            realizedPnl REAL NOT NULL,
            updatedAtEpochMillis INTEGER NOT NULL,
            PRIMARY KEY(epochDay, instrumentId),
            CHECK(quantity >= 0),
            CHECK(costBasis >= 0)
        )
    """.trimIndent()

    val CREATE_INDEX_IMPORTS_CHECKSUM =
        "CREATE UNIQUE INDEX IF NOT EXISTS index_ledger_imports_checksum ON ledger_imports(checksum)"

    val CREATE_INDEX_TRADES_INSTRUMENT_TIME =
        "CREATE INDEX IF NOT EXISTS index_trades_instrument_time ON trades(instrumentId, executedAtEpochMillis)"

    val CREATE_INDEX_TRADES_STRATEGY =
        "CREATE INDEX IF NOT EXISTS index_trades_strategy ON trades(strategyId)"

    val CREATE_INDEX_TRADES_IMPORT_BATCH =
        "CREATE INDEX IF NOT EXISTS index_trades_import_batch ON trades(importBatchId)"

    val CREATE_INDEX_FEES_TRADE =
        "CREATE INDEX IF NOT EXISTS index_trade_fees_trade_id ON trade_fees(tradeId)"

    val CREATE_INDEX_CASH_OCCURRED =
        "CREATE INDEX IF NOT EXISTS index_cash_events_occurred_at ON cash_events(occurredAtEpochMillis)"

    val CREATE_INDEX_SPLITS_INSTRUMENT_DAY =
        "CREATE INDEX IF NOT EXISTS index_split_events_instrument_day ON split_events(instrumentId, exDateEpochDay)"

    /** Statements executed by the v1→v2 migration, in dependency order. */
    val SQL_1_2: List<String> = listOf(
        CREATE_STRATEGIES,
        CREATE_LEDGER_IMPORTS,
        CREATE_TRADES,
        CREATE_TRADE_FEES,
        CREATE_CASH_EVENTS,
        CREATE_SPLIT_EVENTS,
        CREATE_POSITION_SNAPSHOTS,
        CREATE_INDEX_IMPORTS_CHECKSUM,
        CREATE_INDEX_TRADES_INSTRUMENT_TIME,
        CREATE_INDEX_TRADES_STRATEGY,
        CREATE_INDEX_TRADES_IMPORT_BATCH,
        CREATE_INDEX_FEES_TRADE,
        CREATE_INDEX_CASH_OCCURRED,
        CREATE_INDEX_SPLITS_INSTRUMENT_DAY,
    )
}

object TradingMigrations {
    /** Personal database v1 (watchlist only) → v2 (trading ledger tables). */
    val MIGRATION_1_2: Migration = object : Migration(1, 2) {
        override fun migrate(db: SupportSQLiteDatabase) {
            TradingSchema.SQL_1_2.forEach(db::execSQL)
        }
    }
}
