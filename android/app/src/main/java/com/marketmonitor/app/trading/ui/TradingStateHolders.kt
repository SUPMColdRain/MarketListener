package com.marketmonitor.app.trading.ui

import com.marketmonitor.app.trading.TradeSide
import com.marketmonitor.app.trading.TradeView
import java.time.OffsetDateTime
import java.time.format.DateTimeParseException

enum class TradingTab { TRADES, POSITIONS, STATS, REVIEW }

data class TradeFilterState(
    val instrument: String = "",
    val strategy: String = "",
    val side: String = "",
    val fromEpochDay: Long? = null,
    val toEpochDay: Long? = null,
) {
    fun matches(view: TradeView): Boolean {
        val trade = view.trade
        if (instrument.isNotBlank() && !trade.instrumentId.contains(instrument.trim(), ignoreCase = true)) return false
        if (strategy.isNotBlank() && trade.strategyId?.contains(strategy.trim(), ignoreCase = true) != true) return false
        if (side.isNotBlank() && trade.side != side) return false
        val day = trade.executedAtEpochMillis / DAY_MILLIS
        if (fromEpochDay != null && day < fromEpochDay) return false
        if (toEpochDay != null && day > toEpochDay) return false
        return true
    }

    private companion object {
        const val DAY_MILLIS = 86_400_000L
    }
}

data class TradeEntryDraft(
    val instrumentId: String = "",
    val strategyId: String = "",
    val side: String = TradeSide.BUY,
    val quantity: String = "",
    val price: String = "",
    val executedAt: String = "",
    val note: String = "",
    val fees: String = "",
) {
    fun errors(): List<String> {
        val errors = mutableListOf<String>()
        if (instrumentId.isBlank()) errors += "标的不能为空"
        if (side !in setOf(TradeSide.BUY, TradeSide.SELL)) errors += "方向无效"
        val quantityValue = quantity.toLongOrNull()
        if (quantityValue == null || quantityValue <= 0) errors += "数量必须是大于 0 的整数"
        val priceValue = price.toDoubleOrNull()
        if (priceValue == null || priceValue <= 0) errors += "价格必须是大于 0 的数字"
        if (executedAt.isBlank()) {
            errors += "成交时间不能为空"
        } else if (parseEpochMillis(executedAt) == null) {
            errors += "成交时间格式无效（使用 ISO-8601 或毫秒时间戳）"
        }
        fees.split(',').map { it.trim() }.filter { it.isNotEmpty() }.forEach { item ->
            val parts = item.split(':', limit = 2)
            if (parts.size != 2 || parts[0].isBlank()) {
                errors += "费用格式应为 类型:金额（逗号分隔）"
            } else if (parts[1].toDoubleOrNull()?.let { it < 0 } != false) {
                errors += "费用金额不能为负"
            }
        }
        return errors
    }

    fun toFees(): List<Pair<String, Double>> =
        fees.split(',').map { it.trim() }.filter { it.isNotEmpty() }.mapNotNull { item ->
            val parts = item.split(':', limit = 2)
            if (parts.size == 2) parts[0].trim() to parts[1].trim().toDoubleOrNull() else null
        }.filter { it.second != null }.map { it.first to it.second!! }

    fun executedAtEpochMillis(): Long? = parseEpochMillis(executedAt)
}

fun parseEpochMillis(value: String): Long? {
    value.trim().toLongOrNull()?.let { return it }
    return try {
        OffsetDateTime.parse(value.trim()).toInstant().toEpochMilli()
    } catch (_: DateTimeParseException) {
        null
    }
}

data class BackupUiState(
    val password: String = "",
    val busy: Boolean = false,
    val message: String = "",
    val error: String = "",
)

data class TradingUiState(
    val tab: TradingTab = TradingTab.TRADES,
    val filter: TradeFilterState = TradeFilterState(),
    val draft: TradeEntryDraft = TradeEntryDraft(),
    val selectedTradeId: String? = null,
    val editingTradeId: String? = null,
    val backup: BackupUiState = BackupUiState(),
    val error: String = "",
)

fun TradingUiState.withDraft(transform: (TradeEntryDraft) -> TradeEntryDraft): TradingUiState =
    copy(draft = transform(draft))

fun TradingUiState.withFilter(transform: (TradeFilterState) -> TradeFilterState): TradingUiState =
    copy(filter = transform(filter))

fun draftFromTrade(view: TradeView): TradeEntryDraft = TradeEntryDraft(
    instrumentId = view.trade.instrumentId,
    strategyId = view.trade.strategyId.orEmpty(),
    side = view.trade.side,
    quantity = view.trade.quantity.toString(),
    price = view.trade.price.toString(),
    executedAt = view.trade.executedAtEpochMillis.toString(),
    note = view.trade.note.orEmpty(),
    fees = view.fees.joinToString(",") { "${it.kind}:${it.amount}" },
)
