package com.marketmonitor.app.trading

import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.ObjectMapper
import java.security.MessageDigest
import java.time.OffsetDateTime
import java.time.format.DateTimeParseException
import java.util.UUID

class LedgerImportException(message: String) : Exception(message)

data class ImportedLedger(
    val sourceLabel: String,
    val strategies: List<StrategyEntity>,
    val trades: List<TradeEntity>,
    val fees: List<FeeEntity>,
    val cashEvents: List<CashEventEntity>,
)

/**
 * JSON Lines ledger import (FULL-501). One object per line:
 * {"type":"header","source_label":"..."} first, then strategy/trade/cash lines.
 * The whole content checksum is used to reject duplicate imports.
 */
class LedgerImportParser {
    fun parse(content: String, nowEpochMillis: Long, idPrefix: String = "imp"): ImportedLedger {
        val lines = content.lineSequence()
            .map { it.trim() }
            .filter { it.isNotEmpty() }
            .toList()
        if (lines.isEmpty()) throw LedgerImportException("导入文件为空")
        val header = parseLine(lines[0], 1)
        if (header.path("type").asText() != "header") {
            throw LedgerImportException("第 1 行必须是 header")
        }
        val sourceLabel = header.path("source_label").asText("")
        if (sourceLabel.isBlank()) throw LedgerImportException("header 缺少 source_label")

        val strategies = mutableListOf<StrategyEntity>()
        val trades = mutableListOf<TradeEntity>()
        val fees = mutableListOf<FeeEntity>()
        val cashEvents = mutableListOf<CashEventEntity>()

        lines.drop(1).forEachIndexed { index, line ->
            val lineNumber = index + 2
            val node = parseLine(line, lineNumber)
            when (node.path("type").asText()) {
                "strategy" -> strategies += parseStrategy(node, lineNumber, nowEpochMillis)
                "trade" -> {
                    val trade = parseTrade(node, lineNumber, idPrefix, nowEpochMillis)
                    trades += trade.first
                    fees += trade.second
                }
                "cash" -> cashEvents += parseCash(node, lineNumber, idPrefix)
                else -> throw LedgerImportException("第 $lineNumber 行 type 不受支持：${node.path("type").asText()}")
            }
        }
        return ImportedLedger(sourceLabel, strategies, trades, fees, cashEvents)
    }

    fun sha256(content: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(content).joinToString("") { "%02x".format(it) }

    private fun parseLine(line: String, lineNumber: Int): JsonNode = try {
        mapper.readTree(line)
    } catch (_: Exception) {
        throw LedgerImportException("第 $lineNumber 行不是合法 JSON")
    }

    private fun parseStrategy(node: JsonNode, lineNumber: Int, now: Long): StrategyEntity {
        val id = requiredText(node, "id", lineNumber)
        val name = requiredText(node, "name", lineNumber)
        return StrategyEntity(
            id = id,
            name = name,
            description = node.path("description").takeIf { it.isTextual }?.asText(),
            createdAtEpochMillis = now,
        )
    }

    private fun parseTrade(
        node: JsonNode,
        lineNumber: Int,
        idPrefix: String,
        now: Long,
    ): Pair<TradeEntity, List<FeeEntity>> {
        val instrumentId = requiredText(node, "instrument_id", lineNumber)
        val side = requiredText(node, "side", lineNumber).uppercase()
        if (side !in setOf(TradeSide.BUY, TradeSide.SELL)) {
            throw LedgerImportException("第 $lineNumber 行 side 必须是 BUY/SELL")
        }
        val quantity = node.path("quantity").takeIf { it.isIntegralNumber }?.longValue()
            ?: throw LedgerImportException("第 $lineNumber 行 quantity 必须是正整数")
        if (quantity <= 0) throw LedgerImportException("第 $lineNumber 行 quantity 必须大于 0")
        val price = node.path("price").takeIf { it.isNumber }?.doubleValue()
            ?: throw LedgerImportException("第 $lineNumber 行 price 必须是数字")
        if (price <= 0) throw LedgerImportException("第 $lineNumber 行 price 必须大于 0")
        val executedAt = parseTimestamp(node.path("executed_at"), lineNumber, "executed_at")
        val tradeId = "$idPrefix-t-${UUID.randomUUID()}"
        val fees = mutableListOf<FeeEntity>()
        val feesNode = node.path("fees")
        if (feesNode.isArray) {
            feesNode.forEachIndexed { feeIndex, fee ->
                val kind = fee.path("kind").takeIf { it.isTextual }?.asText()
                    ?: throw LedgerImportException("第 $lineNumber 行 fees[$feeIndex] 缺少 kind")
                val amount = fee.path("amount").takeIf { it.isNumber }?.doubleValue()
                    ?: throw LedgerImportException("第 $lineNumber 行 fees[$feeIndex] 缺少 amount")
                if (amount < 0) throw LedgerImportException("第 $lineNumber 行 fees[$feeIndex] amount 不能为负")
                fees += FeeEntity(
                    id = "$idPrefix-f-${UUID.randomUUID()}",
                    tradeId = tradeId,
                    kind = kind,
                    amount = amount,
                    note = fee.path("note").takeIf { it.isTextual }?.asText(),
                )
            }
        } else if (!feesNode.isMissingNode) {
            throw LedgerImportException("第 $lineNumber 行 fees 必须是数组")
        }
        return Pair(
            TradeEntity(
                id = tradeId,
                instrumentId = instrumentId,
                strategyId = node.path("strategy_id").takeIf { it.isTextual }?.asText(),
                side = side,
                quantity = quantity,
                price = price,
                executedAtEpochMillis = executedAt,
                status = TradeStatus.EXECUTED,
                orderGroupId = node.path("order_group_id").takeIf { it.isTextual }?.asText(),
                note = node.path("note").takeIf { it.isTextual }?.asText(),
                createdAtEpochMillis = now,
                updatedAtEpochMillis = now,
            ),
            fees,
        )
    }

    private fun parseCash(node: JsonNode, lineNumber: Int, idPrefix: String): CashEventEntity {
        val kind = requiredText(node, "kind", lineNumber).uppercase()
        if (kind !in setOf(
                CashKind.DEPOSIT,
                CashKind.WITHDRAWAL,
                CashKind.DIVIDEND,
                CashKind.TAX_REFUND,
                CashKind.OTHER,
            )
        ) {
            throw LedgerImportException("第 $lineNumber 行 kind 不受支持：$kind")
        }
        val amount = node.path("amount").takeIf { it.isNumber }?.doubleValue()
            ?: throw LedgerImportException("第 $lineNumber 行 amount 必须是数字")
        if (amount == 0.0) throw LedgerImportException("第 $lineNumber 行 amount 不能为 0")
        return CashEventEntity(
            id = "$idPrefix-c-${UUID.randomUUID()}",
            kind = kind,
            amount = amount,
            occurredAtEpochMillis = parseTimestamp(node.path("occurred_at"), lineNumber, "occurred_at"),
            note = node.path("note").takeIf { it.isTextual }?.asText(),
        )
    }

    private fun parseTimestamp(node: JsonNode, lineNumber: Int, field: String): Long {
        if (node.isIntegralNumber) return node.longValue()
        if (node.isTextual) {
            return try {
                OffsetDateTime.parse(node.asText()).toInstant().toEpochMilli()
            } catch (_: DateTimeParseException) {
                throw LedgerImportException("第 $lineNumber 行 $field 不是合法 ISO-8601 时间")
            }
        }
        throw LedgerImportException("第 $lineNumber 行缺少 $field")
    }

    private fun requiredText(node: JsonNode, field: String, lineNumber: Int): String {
        val value = node.path(field).takeIf { it.isTextual }?.asText()?.trim().orEmpty()
        if (value.isBlank()) throw LedgerImportException("第 $lineNumber 行缺少 $field")
        return value
    }

    private companion object {
        val mapper = ObjectMapper()
    }
}
