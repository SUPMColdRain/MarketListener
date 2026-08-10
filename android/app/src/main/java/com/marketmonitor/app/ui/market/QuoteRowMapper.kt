package com.marketmonitor.app.ui.market

import com.marketmonitor.app.data.ImportedInstrument
import com.marketmonitor.app.ui.data.UiMetricPoint
import java.util.Locale
import kotlin.math.abs

/** One compact quote row derived only from real, finite imported candles. */
data class QuoteRow(
    val instrumentId: String,
    val label: String,
    val code: String,
    val period: String,
    val latestPrice: Double?,
    val previousClose: Double?,
    val changePct: Double?,
    val sparklinePoints: List<UiMetricPoint>,
)

/**
 * Maps an imported instrument to the dense quote row shown on the market page.
 * Missing or non-finite values stay null; the UI must never display zero as a
 * substitute for missing data.
 */
fun quoteRowFor(instrument: ImportedInstrument): QuoteRow {
    val period = preferredPeriod(instrument)
    val candles = instrument.candlesByPeriod[period].orEmpty()
    val closes = candles.mapNotNull { candle -> candle.close.takeIf { it.isFinite() } }
    val displayCode = if (instrument.label.contains(" · ")) {
        instrument.label.substringBefore(" · ")
    } else {
        instrument.instrumentId
    }
    val latestPrice = closes.lastOrNull()
    val previousClose = closes.getOrNull(closes.size - 2)
    val changePct = if (latestPrice != null && previousClose != null && previousClose != 0.0) {
        (latestPrice - previousClose) / previousClose * 100.0
    } else {
        null
    }
    val sparklinePoints = candles.mapNotNull { candle ->
        val close = candle.close.takeIf { it.isFinite() } ?: return@mapNotNull null
        UiMetricPoint(
            epochMillis = candle.openTimeSeconds * 1000L,
            value = close,
            label = "",
        )
    }
    return QuoteRow(
        instrumentId = instrument.instrumentId,
        label = instrument.label,
        code = displayCode,
        period = period,
        latestPrice = latestPrice,
        previousClose = previousClose,
        changePct = changePct,
        sparklinePoints = sparklinePoints,
    )
}

/** Compact, locale-stable price without padding zeros (e.g. 1520.21). */
fun formatQuotePrice(value: Double): String =
    String.format(Locale.US, "%.3f", value).trimEnd('0').trimEnd('.')

/** Signed percentage with exactly two decimals, never "-0.00%". */
fun formatQuoteChangePct(value: Double): String {
    val normalized = if (abs(value) < 0.005) 0.0 else value
    return String.format(Locale.US, "%+.2f%%", normalized)
}
