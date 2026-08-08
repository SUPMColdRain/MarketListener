package com.marketmonitor.app.market

import com.marketmonitor.app.data.ImportedMarketData
import java.time.Instant
import java.time.OffsetDateTime

/**
 * Pure overview/quality aggregation over an imported market snapshot.
 *
 * Missing, failed or stale data is surfaced explicitly; it is never rendered
 * as zero or normal by the UI layer.
 */
data class QualityCounts(
    val pass: Int,
    val warning: Int,
    val failed: Int,
) {
    val hasAnomalies: Boolean get() = failed > 0 || warning > 0
}

data class InstrumentOverview(
    val instrumentId: String,
    val label: String,
    val periods: List<String>,
    val candleCount: Int,
    val quality: QualityCounts,
) {
    val hasAnomalies: Boolean get() = quality.hasAnomalies
}

data class MarketOverview(
    val packageId: String?,
    val dataCutoff: String?,
    val stale: Boolean,
    val instruments: List<InstrumentOverview>,
) {
    val anomalyCount: Int get() = instruments.count { it.hasAnomalies }
    val totalCandles: Int get() = instruments.sumOf { it.candleCount }

    companion object {
        fun compute(
            marketData: ImportedMarketData?,
            now: Instant = Instant.now(),
            staleAfterSeconds: Long = 24L * 3600L,
        ): MarketOverview {
            if (marketData == null) {
                return MarketOverview(packageId = null, dataCutoff = null, stale = true, instruments = emptyList())
            }
            val cutoffInstant = parseCutoff(marketData.dataCutoff)
            val stale = cutoffInstant == null || (now.toEpochMilli() - cutoffInstant.toEpochMilli()) > staleAfterSeconds * 1000L
            val instruments = marketData.instruments.map { instrument ->
                val counts = mutableMapOf("PASS" to 0, "WARNING" to 0, "FAILED" to 0)
                var candleCount = 0
                instrument.candlesByPeriod.values.forEach { candles ->
                    candleCount += candles.size
                    candles.forEach { candle ->
                        counts[candle.qualityStatus] = (counts[candle.qualityStatus] ?: 0) + 1
                    }
                }
                InstrumentOverview(
                    instrumentId = instrument.instrumentId,
                    label = instrument.label,
                    periods = instrument.candlesByPeriod.keys.toList(),
                    candleCount = candleCount,
                    quality = QualityCounts(
                        pass = counts["PASS"] ?: 0,
                        warning = counts["WARNING"] ?: 0,
                        failed = counts["FAILED"] ?: 0,
                    ),
                )
            }
            return MarketOverview(marketData.packageId, marketData.dataCutoff, stale, instruments)
        }

        private fun parseCutoff(value: String?): Instant? = try {
            OffsetDateTime.parse(value).toInstant()
        } catch (_: Exception) {
            null
        }
    }
}
