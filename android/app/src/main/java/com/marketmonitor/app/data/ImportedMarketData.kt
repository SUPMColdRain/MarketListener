package com.marketmonitor.app.data

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import org.json.JSONObject
import java.io.File
import java.time.OffsetDateTime

data class MarketCandle(
    val openTimeSeconds: Long,
    val open: Double,
    val high: Double,
    val low: Double,
    val close: Double,
    val source: String,
    val qualityStatus: String,
)

data class ImportedInstrument(
    val instrumentId: String,
    val label: String,
    val candlesByPeriod: Map<String, List<MarketCandle>>,
)

data class MarketMetric(
    val metricId: String,
    val instrumentId: String,
    val tradingDate: String,
    val period: String,
    val metricName: String,
    val value: Double,
    val definition: String,
    val calculationMethod: String,
    val timestamp: String,
)

data class ImportedMarketData(
    val packageId: String,
    val dataCutoff: String,
    val instruments: List<ImportedInstrument>,
    val metrics: List<MarketMetric> = emptyList(),
)

class ImportedMarketDataReader(private val context: Context) {
    fun readActive(): ImportedMarketData? {
        val preferences = context.getSharedPreferences("market-package", Context.MODE_PRIVATE)
        val packageId = preferences.getString("active", null) ?: return null
        val payload = File(File(DatabaseBoundary.coldDirectory(context), "packages"), "$packageId/payload.sqlite")
        if (!payload.isFile) return null

        SQLiteDatabase.openDatabase(payload.path, null, SQLiteDatabase.OPEN_READONLY).use { database ->
            val instruments = mutableListOf<ImportedInstrument>()
            database.rawQuery(
                "SELECT instrument_id, instrument_json FROM instruments ORDER BY instrument_id",
                null,
            ).use { cursor ->
                while (cursor.moveToNext()) {
                    val instrumentId = cursor.getString(0)
                    val label = instrumentLabel(cursor.getString(1), instrumentId)
                    val periods = periodsFor(database, instrumentId)
                    instruments += ImportedInstrument(instrumentId, label, periods)
                }
            }
            val metrics = readGoldMetrics(database)
            return ImportedMarketData(
                packageId = packageId,
                dataCutoff = preferences.getString("active_cutoff", null) ?: "未记录",
                instruments = instruments,
                metrics = metrics,
            )
        }
    }

    private fun readGoldMetrics(database: SQLiteDatabase): List<MarketMetric> {
        val hasTable = database.rawQuery("PRAGMA table_info(gold_metrics)", null).use { cursor ->
            cursor.moveToFirst()
        }
        if (!hasTable) return emptyList()
        val metrics = mutableListOf<MarketMetric>()
        database.rawQuery(
            "SELECT metric_id, instrument_id, trading_date, period, metric_name, value, definition, calculation_method, timestamp " +
                "FROM gold_metrics ORDER BY trading_date DESC, metric_id",
            null,
        ).use { cursor ->
            while (cursor.moveToNext()) {
                val json = JSONObject()
                    .put("metric_id", cursor.getString(0))
                    .put("instrument_id", cursor.getString(1))
                    .put("trading_date", cursor.getString(2))
                    .put("period", cursor.getString(3))
                    .put("metric_name", cursor.getString(4))
                    .put("value", cursor.getDouble(5))
                    .put("definition", cursor.getString(6))
                    .put("calculation_method", cursor.getString(7))
                    .put("timestamp", cursor.getString(8))
                decodeMarketMetric(json.toString())?.let(metrics::add)
            }
        }
        return metrics
    }

    private fun periodsFor(database: SQLiteDatabase, instrumentId: String): Map<String, List<MarketCandle>> {
        val periods = mutableListOf<String>()
        database.rawQuery(
            "SELECT DISTINCT period FROM bars WHERE instrument_id = ? ORDER BY CASE period WHEN '1d' THEN 0 ELSE 1 END, period",
            arrayOf(instrumentId),
        ).use { cursor -> while (cursor.moveToNext()) periods += cursor.getString(0) }
        return periods.associateWith { period -> candlesFor(database, instrumentId, period) }
    }

    private fun candlesFor(database: SQLiteDatabase, instrumentId: String, period: String): List<MarketCandle> {
        val candles = mutableListOf<MarketCandle>()
        database.rawQuery(
            "SELECT bar_json FROM bars WHERE instrument_id = ? AND period = ? ORDER BY bar_open_time DESC LIMIT 600",
            arrayOf(instrumentId, period),
        ).use { cursor ->
            while (cursor.moveToNext()) {
                decodeMarketCandle(cursor.getString(0))?.let(candles::add)
            }
        }
        return candles.asReversed()
    }
}

internal fun decodeMarketCandle(barJson: String): MarketCandle? = try {
    val bar = JSONObject(barJson)
    MarketCandle(
        openTimeSeconds = OffsetDateTime.parse(bar.getString("bar_open_time")).toEpochSecond(),
        open = bar.getDouble("open"),
        high = bar.getDouble("high"),
        low = bar.getDouble("low"),
        close = bar.getDouble("close"),
        source = bar.getJSONObject("source").getString("provider"),
        qualityStatus = bar.getString("quality_status"),
    )
} catch (_: Exception) {
    null
}

internal fun decodeMarketMetric(metricJson: String): MarketMetric? = try {
    val metric = JSONObject(metricJson)
    MarketMetric(
        metricId = metric.getString("metric_id"),
        instrumentId = metric.getString("instrument_id"),
        tradingDate = metric.getString("trading_date"),
        period = metric.getString("period"),
        metricName = metric.getString("metric_name"),
        value = metric.getDouble("value"),
        definition = metric.optString("definition"),
        calculationMethod = metric.optString("calculation_method"),
        timestamp = metric.optString("timestamp"),
    )
} catch (_: Exception) {
    null
}

private fun instrumentLabel(instrumentJson: String, fallback: String): String = try {
    val key = JSONObject(instrumentJson)
    "${key.getString("code")} · ${key.getString("exchange")} · ${key.getString("asset_type")}"
} catch (_: Exception) {
    fallback
}
