package com.marketmonitor.app.trading

import kotlin.math.round

data class LedgerFee(
    val kind: String,
    val amount: Double,
)

data class LedgerTrade(
    val id: String,
    val instrumentId: String,
    val strategyId: String? = null,
    val side: String,
    val quantity: Long,
    val price: Double,
    val executedAtEpochMillis: Long,
    val status: String = TradeStatus.EXECUTED,
    val parentTradeId: String? = null,
    val orderGroupId: String? = null,
    val createdAtEpochMillis: Long = 0L,
    val fees: List<LedgerFee> = emptyList(),
)

data class CashLedgerEvent(
    val id: String,
    val kind: String,
    val amount: Double,
    val occurredAtEpochMillis: Long,
)

data class SplitLedgerEvent(
    val id: String,
    val instrumentId: String,
    val exDateEpochDay: Long,
    val newPerOld: Double,
)

data class OpenPosition(
    val instrumentId: String,
    val quantity: Long,
    val costBasis: Double,
) {
    val averageCost: Double get() = if (quantity == 0L) 0.0 else costBasis / quantity
}

data class LedgerSnapshot(
    val epochDay: Long,
    val cash: Double,
    val positions: Map<String, OpenPosition>,
    val realizedPnlTotal: Double,
    val feesTotal: Double,
)

data class PositionResult(
    val snapshots: List<LedgerSnapshot>,
    val closedTradePnl: Map<String, Double>,
    val totalFees: Double,
    val executedTrades: List<LedgerTrade>,
) {
    val finalSnapshot: LedgerSnapshot
        get() = snapshots.lastOrNull() ?: LedgerSnapshot(
            epochDay = 0,
            cash = 0.0,
            positions = emptyMap(),
            realizedPnlTotal = 0.0,
            feesTotal = 0.0,
        )
}

class PositionException(message: String) : IllegalArgumentException(message)

/**
 * Average-cost position ledger over daily snapshots.
 *
 * Rules (fixed and documented for the acceptance ledger samples):
 * - Only EXECUTED trades count; REVISED and CANCELLED rows are ignored.
 * - BUY increases quantity and adds price*quantity + fees to the cost basis.
 * - SELL realizes (price*quantity - fees) - averageCost*quantity and never goes short.
 * - Splits multiply quantity by newPerOld at the start of the ex-date and keep the
 *   total cost basis unchanged (average cost divides by newPerOld).
 * - Cash events (deposits positive, withdrawals negative) only move the cash leg.
 */
class PositionCalculator {
    fun calculate(
        trades: List<LedgerTrade>,
        cashEvents: List<CashLedgerEvent> = emptyList(),
        splits: List<SplitLedgerEvent> = emptyList(),
    ): PositionResult {
        val executed = trades
            .filter { it.status == TradeStatus.EXECUTED }
            .sortedWith(compareBy({ it.executedAtEpochMillis }, { it.createdAtEpochMillis }, { it.id }))
        val cash = cashEvents.sortedBy { it.occurredAtEpochMillis }
        val splitByDay = splits.groupBy { it.exDateEpochDay }

        val tradeByDay = executed.groupBy { epochDayOf(it.executedAtEpochMillis) }
        val cashByDay = cash.groupBy { epochDayOf(it.occurredAtEpochMillis) }
        val days = (tradeByDay.keys + cashByDay.keys + splitByDay.keys).sorted()

        var currentCash = 0.0
        val positions = mutableMapOf<String, OpenPosition>()
        var realizedTotal = 0.0
        var feesTotal = 0.0
        val closedPnl = mutableMapOf<String, Double>()
        val snapshots = mutableListOf<LedgerSnapshot>()

        for (day in days) {
            splitByDay[day].orEmpty().forEach { split ->
                positions[split.instrumentId]?.let { position ->
                    val newQuantity = round(position.quantity * split.newPerOld).toLong()
                    positions[split.instrumentId] = OpenPosition(split.instrumentId, newQuantity, position.costBasis)
                }
            }
            cashByDay[day].orEmpty().forEach { currentCash += it.amount }
            tradeByDay[day].orEmpty().forEach { trade ->
                val tradeFees = trade.fees.sumOf { it.amount }
                feesTotal += tradeFees
                when (trade.side) {
                    TradeSide.BUY -> {
                        val position = positions[trade.instrumentId]
                        val quantity = position?.quantity ?: 0L
                        val costBasis = position?.costBasis ?: 0.0
                        positions[trade.instrumentId] = OpenPosition(
                            trade.instrumentId,
                            quantity + trade.quantity,
                            costBasis + trade.price * trade.quantity + tradeFees,
                        )
                        currentCash -= trade.price * trade.quantity + tradeFees
                    }

                    TradeSide.SELL -> {
                        val position = positions[trade.instrumentId]
                            ?: throw PositionException(
                                "SELL ${trade.id} exceeds position for ${trade.instrumentId} (no position)",
                            )
                        if (trade.quantity > position.quantity) {
                            throw PositionException(
                                "SELL ${trade.id} exceeds position for ${trade.instrumentId}: " +
                                    "have ${position.quantity}, sell ${trade.quantity}",
                            )
                        }
                        val pnl = trade.price * trade.quantity - tradeFees - position.averageCost * trade.quantity
                        realizedTotal += pnl
                        closedPnl[trade.id] = pnl
                        val remaining = position.quantity - trade.quantity
                        positions[trade.instrumentId] = OpenPosition(
                            trade.instrumentId,
                            remaining,
                            if (remaining == 0L) 0.0 else position.costBasis - position.averageCost * trade.quantity,
                        )
                        currentCash += trade.price * trade.quantity - tradeFees
                    }

                    else -> throw PositionException("Unknown side ${trade.side} on trade ${trade.id}")
                }
            }
            snapshots += LedgerSnapshot(
                epochDay = day,
                cash = currentCash,
                positions = positions.toMap(),
                realizedPnlTotal = realizedTotal,
                feesTotal = feesTotal,
            )
        }
        return PositionResult(
            snapshots = snapshots,
            closedTradePnl = closedPnl,
            totalFees = feesTotal,
            executedTrades = executed,
        )
    }
}

internal fun epochDayOf(epochMillis: Long): Long = Math.floorDiv(epochMillis, MILLIS_PER_DAY)

private const val MILLIS_PER_DAY = 86_400_000L
