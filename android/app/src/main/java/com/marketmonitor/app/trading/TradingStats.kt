package com.marketmonitor.app.trading

data class DailyClose(
    val epochDay: Long,
    val instrumentId: String,
    val close: Double,
)

data class NavPoint(
    val epochDay: Long,
    val nav: Double,
    val cash: Double,
    val positionValue: Double,
    val exposurePct: Double,
    val markedWithFallback: Boolean,
)

data class TradingStatsResult(
    val navCurve: List<NavPoint>,
    val totalReturnPct: Double,
    val maxDrawdownPct: Double,
    val winRatePct: Double,
    val profitFactor: Double?,
    val grossProfit: Double,
    val grossLoss: Double,
    val averageExposurePct: Double,
    val maxExposurePct: Double,
    val realizedByStrategy: Map<String, Double>,
    val realizedByInstrument: Map<String, Double>,
    val unrealizedByStrategy: Map<String, Double>,
    val unrealizedByInstrument: Map<String, Double>,
    val realizedTotal: Double,
    val feesTotal: Double,
)

/**
 * NAV/risk/attribution statistics over the ledger snapshots produced by
 * [PositionCalculator].
 *
 * Conventions (fixed for the acceptance samples):
 * - NAV = cash + mark-to-market position value. Missing closes fall back to the
 *   last known close for the instrument, then to average cost; fallback is flagged.
 * - Win rate counts closed trades with realized PnL > 0; breakeven counts as a
 *   non-win. Profit factor is gross profit / gross loss and null when gross loss is 0.
 * - Exposure is |position value| / NAV (long-only positions, so position value ≥ 0).
 * - Attribution: realized PnL per strategy/instrument plus unrealized PnL of open
 *   positions attributed to the strategy of the latest executed trade per instrument.
 */
class TradingStatsCalculator {
    fun calculate(result: PositionResult, closes: List<DailyClose>): TradingStatsResult {
        val pricesByDay = closes.groupBy { it.epochDay }
        val days = (result.snapshots.map { it.epochDay } + pricesByDay.keys).toSortedSet()
        val lastClose = mutableMapOf<String, Double>()
        val navPoints = mutableListOf<NavPoint>()
        var snapshotIndex = 0

        for (day in days) {
            while (snapshotIndex < result.snapshots.size && result.snapshots[snapshotIndex].epochDay <= day) {
                snapshotIndex += 1
            }
            val snapshot = if (snapshotIndex == 0) {
                LedgerSnapshot(day, 0.0, emptyMap(), 0.0, 0.0)
            } else {
                result.snapshots[snapshotIndex - 1]
            }
            pricesByDay[day].orEmpty().forEach { lastClose[it.instrumentId] = it.close }
            var positionValue = 0.0
            var markedWithFallback = false
            snapshot.positions.values.forEach { position ->
                val close = lastClose[position.instrumentId]
                if (close != null) {
                    positionValue += close * position.quantity
                } else {
                    markedWithFallback = true
                    positionValue += position.costBasis
                }
            }
            val nav = snapshot.cash + positionValue
            val exposurePct = if (nav == 0.0) 0.0 else positionValue / nav * 100.0
            navPoints += NavPoint(day, nav, snapshot.cash, positionValue, exposurePct, markedWithFallback)
        }

        val totalReturnPct = if (navPoints.isEmpty() || navPoints.first().nav == 0.0) {
            0.0
        } else {
            (navPoints.last().nav - navPoints.first().nav) / navPoints.first().nav * 100.0
        }

        var peak = Double.NEGATIVE_INFINITY
        var maxDrawdownPct = 0.0
        navPoints.forEach { point ->
            if (point.nav > peak) peak = point.nav
            if (peak > 0.0) maxDrawdownPct = maxOf(maxDrawdownPct, (peak - point.nav) / peak * 100.0)
        }

        val pnls = result.closedTradePnl.values
        val closed = pnls.size
        val wins = pnls.count { it > 0.0 }
        val winRatePct = if (closed == 0) 0.0 else wins.toDouble() / closed * 100.0
        val grossProfit = pnls.filter { it > 0.0 }.sum()
        val grossLoss = pnls.filter { it < 0.0 }.sumOf { -it }
        val profitFactor = if (grossLoss == 0.0) null else grossProfit / grossLoss

        val exposurePoints = navPoints.filter { it.nav != 0.0 }.map { it.exposurePct }
        val averageExposurePct = if (exposurePoints.isEmpty()) 0.0 else exposurePoints.average()
        val maxExposurePct = exposurePoints.maxOrNull() ?: 0.0

        val realizedByStrategy = mutableMapOf<String, Double>()
        val realizedByInstrument = mutableMapOf<String, Double>()
        result.executedTrades.forEach { trade ->
            val pnl = result.closedTradePnl[trade.id] ?: 0.0
            realizedByStrategy.merge(trade.strategyId ?: UNASSIGNED, pnl, Double::plus)
            realizedByInstrument.merge(trade.instrumentId, pnl, Double::plus)
        }

        val unrealizedByStrategy = mutableMapOf<String, Double>()
        val unrealizedByInstrument = mutableMapOf<String, Double>()
        result.finalSnapshot.positions.values.forEach { position ->
            val close = lastClose[position.instrumentId]
            val value = if (close != null) close * position.quantity else position.costBasis
            val unrealized = value - position.costBasis
            val strategy = result.executedTrades
                .asReversed()
                .firstOrNull { it.instrumentId == position.instrumentId }
                ?.strategyId ?: UNASSIGNED
            unrealizedByStrategy.merge(strategy, unrealized, Double::plus)
            unrealizedByInstrument.merge(position.instrumentId, unrealized, Double::plus)
        }

        return TradingStatsResult(
            navCurve = navPoints,
            totalReturnPct = totalReturnPct,
            maxDrawdownPct = maxDrawdownPct,
            winRatePct = winRatePct,
            profitFactor = profitFactor,
            grossProfit = grossProfit,
            grossLoss = grossLoss,
            averageExposurePct = averageExposurePct,
            maxExposurePct = maxExposurePct,
            realizedByStrategy = realizedByStrategy,
            realizedByInstrument = realizedByInstrument,
            unrealizedByStrategy = unrealizedByStrategy,
            unrealizedByInstrument = unrealizedByInstrument,
            realizedTotal = realizedTotal(result),
            feesTotal = result.totalFees,
        )
    }

    private fun realizedTotal(result: PositionResult): Double = result.closedTradePnl.values.sum()

    companion object {
        const val UNASSIGNED = "UNASSIGNED"
    }
}
