package com.marketmonitor.app.trading

import androidx.room.withTransaction
import com.marketmonitor.app.data.UserDatabase
import com.marketmonitor.app.data.WatchlistEntity
import java.io.File
import java.util.UUID

data class FeeInput(val kind: String, val amount: Double)

data class TradeInput(
    val instrumentId: String,
    val strategyId: String? = null,
    val side: String,
    val quantity: Long,
    val price: Double,
    val executedAtEpochMillis: Long,
    val orderGroupId: String? = null,
    val note: String? = null,
    val fees: List<FeeInput> = emptyList(),
)

class TradeInputValidator {
    fun errors(input: TradeInput): List<String> {
        val errors = mutableListOf<String>()
        if (input.instrumentId.isBlank()) errors += "标的不能为空"
        if (input.side !in setOf(TradeSide.BUY, TradeSide.SELL)) errors += "方向必须是买入或卖出"
        if (input.quantity <= 0) errors += "数量必须大于 0"
        if (input.price <= 0) errors += "价格必须大于 0"
        if (input.executedAtEpochMillis <= 0) errors += "成交时间无效"
        input.fees.forEachIndexed { index, fee ->
            if (fee.kind.isBlank()) errors += "第 ${index + 1} 笔费用缺少类型"
            if (fee.amount < 0) errors += "第 ${index + 1} 笔费用金额不能为负"
        }
        return errors
    }
}

data class TradeView(
    val trade: TradeEntity,
    val fees: List<FeeEntity>,
) {
    val totalFee: Double get() = fees.sumOf { it.amount }
    val realizedPnl: Double? get() = null
}

data class PositionView(
    val instrumentId: String,
    val quantity: Long,
    val averageCost: Double,
    val costBasis: Double,
    val realizedPnl: Double,
)

sealed class LedgerImportResult {
    data class Imported(val batchId: String, val tradeCount: Int, val cashCount: Int, val strategyCount: Int) :
        LedgerImportResult()

    data class Duplicate(val checksum: String) : LedgerImportResult()
}

data class RestoreResult(val counts: Map<String, Int>)

class DuplicateImportException(val checksum: String) : Exception("duplicate ledger import")

/** Android glue between Room and the pure ledger/backup/statistics domain. */
class TradingRepository(
    private val database: UserDatabase,
    private val clock: () -> Long = System::currentTimeMillis,
) {
    private val dao get() = database.tradingDao()
    private val validator = TradeInputValidator()
    private val calculator = PositionCalculator()
    private val statsCalculator = TradingStatsCalculator()
    private val codec = PersonalBackupCodec()

    suspend fun strategies(): List<StrategyEntity> = dao.strategies()

    suspend fun addTrade(input: TradeInput): TradeEntity {
        val errors = validator.errors(input)
        if (errors.isNotEmpty()) throw IllegalArgumentException(errors.joinToString("；"))
        val now = clock()
        val trade = TradeEntity(
            id = "t-${UUID.randomUUID()}",
            instrumentId = input.instrumentId,
            strategyId = input.strategyId,
            side = input.side,
            quantity = input.quantity,
            price = input.price,
            executedAtEpochMillis = input.executedAtEpochMillis,
            status = TradeStatus.EXECUTED,
            orderGroupId = input.orderGroupId,
            note = input.note,
            createdAtEpochMillis = now,
            updatedAtEpochMillis = now,
        )
        database.withTransaction {
            dao.insertTrade(trade)
            dao.insertFees(input.fees.map { fee ->
                FeeEntity(
                    id = "f-${UUID.randomUUID()}",
                    tradeId = trade.id,
                    kind = fee.kind,
                    amount = fee.amount,
                )
            })
        }
        return trade
    }

    suspend fun reviseTrade(parentTradeId: String, input: TradeInput): TradeEntity {
        val errors = validator.errors(input)
        if (errors.isNotEmpty()) throw IllegalArgumentException(errors.joinToString("；"))
        val parent = dao.tradeById(parentTradeId) ?: throw IllegalArgumentException("原交易不存在：$parentTradeId")
        if (parent.status != TradeStatus.EXECUTED) {
            throw IllegalArgumentException("只有已成交交易可以修订")
        }
        val now = clock()
        val revision = TradeEntity(
            id = "t-${UUID.randomUUID()}",
            instrumentId = input.instrumentId,
            strategyId = input.strategyId,
            side = input.side,
            quantity = input.quantity,
            price = input.price,
            executedAtEpochMillis = input.executedAtEpochMillis,
            status = TradeStatus.EXECUTED,
            parentTradeId = parent.id,
            orderGroupId = input.orderGroupId,
            note = input.note,
            createdAtEpochMillis = now,
            updatedAtEpochMillis = now,
        )
        database.withTransaction {
            dao.updateTradeStatus(parent.id, TradeStatus.REVISED, now)
            dao.insertTrade(revision)
            dao.insertFees(input.fees.map { fee ->
                FeeEntity(
                    id = "f-${UUID.randomUUID()}",
                    tradeId = revision.id,
                    kind = fee.kind,
                    amount = fee.amount,
                )
            })
        }
        return revision
    }

    suspend fun cancelTrade(tradeId: String) {
        val trade = dao.tradeById(tradeId) ?: throw IllegalArgumentException("交易不存在：$tradeId")
        if (trade.status != TradeStatus.EXECUTED) throw IllegalArgumentException("只有已成交交易可以撤销")
        dao.updateTradeStatus(tradeId, TradeStatus.CANCELLED, clock())
    }

    suspend fun importLedger(content: String, sourceLabel: String): LedgerImportResult {
        val parser = LedgerImportParser()
        val checksum = parser.sha256(content.toByteArray(Charsets.UTF_8))
        if (dao.importByChecksum(checksum) != null) return LedgerImportResult.Duplicate(checksum)
        val parsed = parser.parse(content, clock())
        val batchId = "batch-${UUID.randomUUID()}"
        return try {
            database.withTransaction {
                if (dao.importByChecksum(checksum) != null) throw DuplicateImportException(checksum)
                dao.insertLedgerImport(
                    LedgerImportEntity(
                        id = batchId,
                        checksum = checksum,
                        sourceLabel = sourceLabel,
                        importedAtEpochMillis = clock(),
                        tradeCount = parsed.trades.size,
                        cashCount = parsed.cashEvents.size,
                    ),
                )
                if (parsed.strategies.isNotEmpty()) dao.upsertStrategies(parsed.strategies)
                if (parsed.trades.isNotEmpty()) {
                    dao.insertTrades(parsed.trades.map { it.copy(importBatchId = batchId) })
                }
                if (parsed.fees.isNotEmpty()) dao.insertFees(parsed.fees)
                if (parsed.cashEvents.isNotEmpty()) {
                    dao.insertCashAll(parsed.cashEvents.map { it.copy(importBatchId = batchId) })
                }
            }
            LedgerImportResult.Imported(
                batchId = batchId,
                tradeCount = parsed.trades.size,
                cashCount = parsed.cashEvents.size,
                strategyCount = parsed.strategies.size,
            )
        } catch (_: DuplicateImportException) {
            LedgerImportResult.Duplicate(checksum)
        }
    }

    suspend fun allTrades(): List<TradeView> {
        val fees = dao.feesAll().groupBy { it.tradeId }
        return dao.tradesAll().map { trade -> TradeView(trade, fees[trade.id].orEmpty()) }
    }

    suspend fun positions(): List<PositionView> {
        val result = calculator.calculate(ledgerTrades(), ledgerCash(), ledgerSplits())
        val realizedByInstrument = mutableMapOf<String, Double>()
        result.executedTrades.forEach { trade ->
            val pnl = result.closedTradePnl[trade.id] ?: 0.0
            realizedByInstrument.merge(trade.instrumentId, pnl, Double::plus)
        }
        return result.finalSnapshot.positions.values.map { position ->
            PositionView(
                instrumentId = position.instrumentId,
                quantity = position.quantity,
                averageCost = position.averageCost,
                costBasis = position.costBasis,
                realizedPnl = realizedByInstrument[position.instrumentId] ?: 0.0,
            )
        }.sortedBy { it.instrumentId }
    }

    suspend fun stats(closes: List<DailyClose>): TradingStatsResult {
        val result = calculator.calculate(ledgerTrades(), ledgerCash(), ledgerSplits())
        return statsCalculator.calculate(result, closes)
    }

    suspend fun exportBackup(password: CharArray, file: File): File {
        val tables = linkedMapOf(
            "strategies" to dao.strategies().map { it.toRow() },
            "ledger_imports" to dao.ledgerImportsAll().map { it.toRow() },
            "trades" to dao.tradesAll().map { it.toRow() },
            "trade_fees" to dao.feesAll().map { it.toRow() },
            "cash_events" to dao.cashEvents().map { it.toRow() },
            "split_events" to dao.splits().map { it.toRow() },
            "position_snapshots" to dao.positionSnapshotsAll().map { it.toRow() },
            "watchlist" to dao.watchlistAll().map { it.toRow() },
        )
        val payload = BackupPayload(
            formatVersion = BACKUP_FORMAT_VERSION,
            appVersion = "0.1.0",
            exportedAtIso = java.time.OffsetDateTime.now().toString(),
            tables = tables,
        )
        file.writeBytes(codec.export(password, payload))
        return file
    }

    suspend fun restoreBackup(password: CharArray, file: File): RestoreResult {
        val payload = codec.import(password, file.readBytes())
        val plan = RestorePlanner().plan(payload)
        val counts = mutableMapOf<String, Int>()
        database.withTransaction {
            plan.deleteOrder.forEach { table -> clearTable(table) }
            plan.insertOrder.forEach { tablePlan ->
                insertTable(tablePlan.table, tablePlan.rows)
                counts[tablePlan.table] = tablePlan.rows.size
            }
        }
        return RestoreResult(counts)
    }

    suspend fun savePositionSnapshots(snapshots: List<PositionSnapshotEntity>) {
        dao.upsertPositionSnapshots(snapshots)
    }

    private suspend fun ledgerTrades(): List<LedgerTrade> {
        val fees = dao.feesAll().groupBy { it.tradeId }
        return dao.tradesAll().map { trade ->
            LedgerTrade(
                id = trade.id,
                instrumentId = trade.instrumentId,
                strategyId = trade.strategyId,
                side = trade.side,
                quantity = trade.quantity,
                price = trade.price,
                executedAtEpochMillis = trade.executedAtEpochMillis,
                status = trade.status,
                parentTradeId = trade.parentTradeId,
                orderGroupId = trade.orderGroupId,
                createdAtEpochMillis = trade.createdAtEpochMillis,
                fees = fees[trade.id].orEmpty().map { LedgerFee(it.kind, it.amount) },
            )
        }
    }

    private suspend fun ledgerCash(): List<CashLedgerEvent> =
        dao.cashEvents().map { CashLedgerEvent(it.id, it.kind, it.amount, it.occurredAtEpochMillis) }

    private suspend fun ledgerSplits(): List<SplitLedgerEvent> =
        dao.splits().map { SplitLedgerEvent(it.id, it.instrumentId, it.exDateEpochDay, it.newPerOld) }

    private suspend fun clearTable(table: String) {
        when (table) {
            "trade_fees" -> dao.clearFees()
            "trades" -> dao.clearTrades()
            "cash_events" -> dao.clearCash()
            "split_events" -> dao.clearSplits()
            "position_snapshots" -> dao.clearPositions()
            "ledger_imports" -> dao.clearImports()
            "strategies" -> dao.clearStrategies()
            "watchlist" -> dao.clearWatchlist()
            else -> throw IllegalArgumentException("未知表：$table")
        }
    }

    private suspend fun insertTable(table: String, rows: List<Map<String, Any?>>) {
        when (table) {
            "strategies" -> dao.upsertStrategies(rows.map(::rowToStrategy))
            "ledger_imports" -> dao.insertLedgerImportsAll(rows.map(::rowToImport))
            "trades" -> dao.insertTrades(rows.map(::rowToTrade))
            "trade_fees" -> dao.insertFees(rows.map(::rowToFee))
            "cash_events" -> dao.insertCashAll(rows.map(::rowToCash))
            "split_events" -> dao.insertSplits(rows.map(::rowToSplit))
            "position_snapshots" -> dao.upsertPositionSnapshots(rows.map(::rowToSnapshot))
            "watchlist" -> dao.insertWatchlistAll(rows.map(::rowToWatchlist))
            else -> throw IllegalArgumentException("未知表：$table")
        }
    }

    private fun StrategyEntity.toRow() = mapOf(
        "id" to id,
        "name" to name,
        "description" to description,
        "createdAtEpochMillis" to createdAtEpochMillis,
    )

    private fun LedgerImportEntity.toRow() = mapOf(
        "id" to id,
        "checksum" to checksum,
        "sourceLabel" to sourceLabel,
        "importedAtEpochMillis" to importedAtEpochMillis,
        "tradeCount" to tradeCount,
        "cashCount" to cashCount,
    )

    private fun TradeEntity.toRow() = mapOf(
        "id" to id,
        "instrumentId" to instrumentId,
        "strategyId" to strategyId,
        "side" to side,
        "quantity" to quantity,
        "price" to price,
        "executedAtEpochMillis" to executedAtEpochMillis,
        "status" to status,
        "parentTradeId" to parentTradeId,
        "orderGroupId" to orderGroupId,
        "importBatchId" to importBatchId,
        "note" to note,
        "createdAtEpochMillis" to createdAtEpochMillis,
        "updatedAtEpochMillis" to updatedAtEpochMillis,
    )

    private fun FeeEntity.toRow() = mapOf(
        "id" to id,
        "tradeId" to tradeId,
        "kind" to kind,
        "amount" to amount,
        "note" to note,
    )

    private fun CashEventEntity.toRow() = mapOf(
        "id" to id,
        "kind" to kind,
        "amount" to amount,
        "occurredAtEpochMillis" to occurredAtEpochMillis,
        "importBatchId" to importBatchId,
        "note" to note,
    )

    private fun SplitEventEntity.toRow() = mapOf(
        "id" to id,
        "instrumentId" to instrumentId,
        "exDateEpochDay" to exDateEpochDay,
        "newPerOld" to newPerOld,
    )

    private fun PositionSnapshotEntity.toRow() = mapOf(
        "epochDay" to epochDay,
        "instrumentId" to instrumentId,
        "quantity" to quantity,
        "costBasis" to costBasis,
        "realizedPnl" to realizedPnl,
        "updatedAtEpochMillis" to updatedAtEpochMillis,
    )

    private fun WatchlistEntity.toRow() = mapOf(
        "instrumentId" to instrumentId,
        "createdAt" to createdAt,
    )

    private fun rowToStrategy(row: Map<String, Any?>) = StrategyEntity(
        id = row.requiredString("id"),
        name = row.requiredString("name"),
        description = row["description"] as? String,
        createdAtEpochMillis = row.requiredLong("createdAtEpochMillis"),
    )

    private fun rowToImport(row: Map<String, Any?>) = LedgerImportEntity(
        id = row.requiredString("id"),
        checksum = row.requiredString("checksum"),
        sourceLabel = row.requiredString("sourceLabel"),
        importedAtEpochMillis = row.requiredLong("importedAtEpochMillis"),
        tradeCount = row.requiredLong("tradeCount").toInt(),
        cashCount = row.requiredLong("cashCount").toInt(),
    )

    private fun rowToTrade(row: Map<String, Any?>) = TradeEntity(
        id = row.requiredString("id"),
        instrumentId = row.requiredString("instrumentId"),
        strategyId = row["strategyId"] as? String,
        side = row.requiredString("side"),
        quantity = row.requiredLong("quantity"),
        price = row.requiredDouble("price"),
        executedAtEpochMillis = row.requiredLong("executedAtEpochMillis"),
        status = row.requiredString("status"),
        parentTradeId = row["parentTradeId"] as? String,
        orderGroupId = row["orderGroupId"] as? String,
        importBatchId = row["importBatchId"] as? String,
        note = row["note"] as? String,
        createdAtEpochMillis = row.requiredLong("createdAtEpochMillis"),
        updatedAtEpochMillis = row.requiredLong("updatedAtEpochMillis"),
    )

    private fun rowToFee(row: Map<String, Any?>) = FeeEntity(
        id = row.requiredString("id"),
        tradeId = row.requiredString("tradeId"),
        kind = row.requiredString("kind"),
        amount = row.requiredDouble("amount"),
        note = row["note"] as? String,
    )

    private fun rowToCash(row: Map<String, Any?>) = CashEventEntity(
        id = row.requiredString("id"),
        kind = row.requiredString("kind"),
        amount = row.requiredDouble("amount"),
        occurredAtEpochMillis = row.requiredLong("occurredAtEpochMillis"),
        importBatchId = row["importBatchId"] as? String,
        note = row["note"] as? String,
    )

    private fun rowToSplit(row: Map<String, Any?>) = SplitEventEntity(
        id = row.requiredString("id"),
        instrumentId = row.requiredString("instrumentId"),
        exDateEpochDay = row.requiredLong("exDateEpochDay"),
        newPerOld = row.requiredDouble("newPerOld"),
    )

    private fun rowToSnapshot(row: Map<String, Any?>) = PositionSnapshotEntity(
        epochDay = row.requiredLong("epochDay"),
        instrumentId = row.requiredString("instrumentId"),
        quantity = row.requiredLong("quantity"),
        costBasis = row.requiredDouble("costBasis"),
        realizedPnl = row.requiredDouble("realizedPnl"),
        updatedAtEpochMillis = row.requiredLong("updatedAtEpochMillis"),
    )

    private fun rowToWatchlist(row: Map<String, Any?>) = WatchlistEntity(
        instrumentId = row.requiredString("instrumentId"),
        createdAt = row.requiredString("createdAt"),
    )

    private fun Map<String, Any?>.requiredString(key: String): String =
        this[key] as? String ?: throw BackupException.CorruptPayload("缺少字符串字段 $key")

    private fun Map<String, Any?>.requiredLong(key: String): Long =
        (this[key] as? Number)?.toLong() ?: throw BackupException.CorruptPayload("缺少数字字段 $key")

    private fun Map<String, Any?>.requiredDouble(key: String): Double =
        (this[key] as? Number)?.toDouble() ?: throw BackupException.CorruptPayload("缺少数字字段 $key")
}
