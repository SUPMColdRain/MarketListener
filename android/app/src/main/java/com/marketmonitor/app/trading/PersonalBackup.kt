package com.marketmonitor.app.trading

import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.ObjectMapper
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.security.SecureRandom
import javax.crypto.AEADBadTagException
import javax.crypto.Cipher
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.PBEKeySpec
import javax.crypto.spec.SecretKeySpec

const val BACKUP_FORMAT_VERSION = 1
const val BACKUP_MAGIC = "MMPB1"

sealed class BackupException(message: String) : Exception(message) {
    class InvalidFormat(message: String = "备份文件格式无效") : BackupException(message)
    class Truncated(message: String = "备份文件被截断") : BackupException(message)
    class WrongPassword(message: String = "密码错误或数据被篡改") : BackupException(message)
    class UnsupportedVersion(message: String = "备份版本不受支持") : BackupException(message)
    class CorruptPayload(message: String = "备份内容损坏") : BackupException(message)
}

data class BackupPayload(
    val formatVersion: Int,
    val appVersion: String,
    val exportedAtIso: String,
    val tables: Map<String, List<Map<String, Any?>>>,
)

/**
 * Versioned, password-encrypted personal-data backup container.
 *
 * Layout: "MMPB1" | version byte | iterations (4 BE) | salt (16) | iv (12) |
 * AES/GCM ciphertext of the JSON payload (PBKDF2-HmacSHA256 derived key).
 * GCM authenticates the payload, so wrong passwords and any ciphertext
 * tampering fail with [BackupException.WrongPassword] before any data is
 * touched by a restore.
 */
class PersonalBackupCodec(
    private val iterations: Int = 210_000,
    private val saltSize: Int = 16,
    private val ivSize: Int = 12,
) {
    private val mapper = ObjectMapper()
    private val random = SecureRandom()

    fun export(password: CharArray, payload: BackupPayload): ByteArray {
        require(payload.formatVersion == BACKUP_FORMAT_VERSION) { "unsupported payload version" }
        val plaintext = mapper.writeValueAsBytes(payload)
        val salt = ByteArray(saltSize).also(random::nextBytes)
        val iv = ByteArray(ivSize).also(random::nextBytes)
        val key = deriveKey(password, salt, iterations)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, iv))
        val ciphertext = cipher.doFinal(plaintext)
        return ByteArrayOutputStream().use { output ->
            output.write(BACKUP_MAGIC.toByteArray(Charsets.US_ASCII))
            output.write(BACKUP_FORMAT_VERSION)
            output.write(ByteBuffer.allocate(4).putInt(iterations).array())
            output.write(salt)
            output.write(iv)
            output.write(ciphertext)
            output.toByteArray()
        }
    }

    fun import(password: CharArray, data: ByteArray): BackupPayload {
        if (data.size < HEADER_SIZE) throw BackupException.Truncated()
        val magic = String(data, 0, 5, Charsets.US_ASCII)
        if (magic != BACKUP_MAGIC) throw BackupException.InvalidFormat()
        val version = data[5].toInt()
        if (version != BACKUP_FORMAT_VERSION) throw BackupException.UnsupportedVersion()
        val header = ByteBuffer.wrap(data, 6, 4)
        val storedIterations = header.int
        val salt = data.copyOfRange(10, 10 + saltSize)
        val iv = data.copyOfRange(10 + saltSize, 10 + saltSize + ivSize)
        val ciphertext = data.copyOfRange(10 + saltSize + ivSize, data.size)
        if (ciphertext.size < 16) throw BackupException.Truncated()
        val key = deriveKey(password, salt, storedIterations)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        val plaintext = try {
            cipher.init(
                Cipher.DECRYPT_MODE,
                SecretKeySpec(key, "AES"),
                GCMParameterSpec(128, iv),
            )
            cipher.doFinal(ciphertext)
        } catch (_: AEADBadTagException) {
            throw BackupException.WrongPassword()
        } catch (_: javax.crypto.BadPaddingException) {
            throw BackupException.WrongPassword()
        }
        val root = try {
            mapper.readTree(ByteArrayInputStream(plaintext))
        } catch (_: Exception) {
            throw BackupException.CorruptPayload()
        }
        val formatVersion = root.path("formatVersion").asInt(-1)
        if (formatVersion != BACKUP_FORMAT_VERSION) throw BackupException.CorruptPayload()
        val tables = parseTables(root.path("tables")) ?: throw BackupException.CorruptPayload()
        if (tables.isEmpty()) throw BackupException.CorruptPayload()
        return BackupPayload(
            formatVersion = formatVersion,
            appVersion = root.path("appVersion").asText(""),
            exportedAtIso = root.path("exportedAtIso").asText(""),
            tables = tables,
        )
    }

    private fun parseTables(node: JsonNode): Map<String, List<Map<String, Any?>>>? {
        if (!node.isObject) return null
        val result = linkedMapOf<String, List<Map<String, Any?>>>()
        node.fields().forEach { (table, rows) ->
            if (!rows.isArray) return null
            val parsed = mutableListOf<Map<String, Any?>>()
            rows.forEach { row ->
                if (!row.isObject) return null
                val fields = linkedMapOf<String, Any?>()
                row.fields().forEach { (name, value) ->
                    when {
                        value.isNull || value.isMissingNode -> fields[name] = null
                        value.isTextual -> fields[name] = value.textValue()
                        value.isIntegralNumber -> fields[name] = value.longValue()
                        value.isFloatingPointNumber -> fields[name] = value.doubleValue()
                        value.isBoolean -> fields[name] = value.booleanValue()
                        else -> return null
                    }
                }
                parsed += fields
            }
            result[table] = parsed
        }
        return result
    }

    private fun deriveKey(password: CharArray, salt: ByteArray, iterationCount: Int): ByteArray {
        val spec = PBEKeySpec(password, salt, iterationCount, KEY_BITS)
        return try {
            SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256")
                .generateSecret(spec)
                .encoded
        } finally {
            spec.clearPassword()
        }
    }

    private companion object {
        const val KEY_BITS = 256
        const val HEADER_SIZE = 38
    }
}

data class TableRestorePlan(
    val table: String,
    val rows: List<Map<String, Any?>>,
)

data class RestorePlan(
    val deleteOrder: List<String>,
    val insertOrder: List<TableRestorePlan>,
)

/** Validates a decrypted payload and orders table application for a transactional restore. */
class RestorePlanner(
    private val allowedTables: Set<String> = DEFAULT_TABLES,
) {
    fun plan(payload: BackupPayload): RestorePlan {
        val unknown = payload.tables.keys - allowedTables
        if (unknown.isNotEmpty()) throw BackupException.CorruptPayload("未知表：${unknown.joinToString()}")
        val expectedColumns = COLUMNS
        payload.tables.forEach { (table, rows) ->
            rows.forEachIndexed { index, row ->
                val extra = row.keys - expectedColumns.getValue(table)
                if (extra.isNotEmpty()) {
                    throw BackupException.CorruptPayload("$table 第 ${index + 1} 行含未知字段：${extra.joinToString()}")
                }
                row.values.forEach { value ->
                    if (value != null && value !is String && value !is Number && value !is Boolean) {
                        throw BackupException.CorruptPayload("$table 第 ${index + 1} 行含不支持的值类型")
                    }
                }
            }
        }
        return RestorePlan(
            deleteOrder = DELETE_ORDER.filter { it in payload.tables },
            insertOrder = INSERT_ORDER.filter { it in payload.tables }
                .map { table -> TableRestorePlan(table, payload.tables.getValue(table)) },
        )
    }

    companion object {
        val DEFAULT_TABLES = setOf(
            "strategies",
            "ledger_imports",
            "trades",
            "trade_fees",
            "cash_events",
            "split_events",
            "position_snapshots",
            "watchlist",
        )

        val DELETE_ORDER = listOf(
            "trade_fees",
            "trades",
            "cash_events",
            "split_events",
            "position_snapshots",
            "ledger_imports",
            "strategies",
            "watchlist",
        )

        val INSERT_ORDER = listOf(
            "strategies",
            "ledger_imports",
            "trades",
            "trade_fees",
            "cash_events",
            "split_events",
            "position_snapshots",
            "watchlist",
        )

        private val COLUMNS = mapOf(
            "strategies" to setOf("id", "name", "description", "createdAtEpochMillis"),
            "ledger_imports" to setOf(
                "id",
                "checksum",
                "sourceLabel",
                "importedAtEpochMillis",
                "tradeCount",
                "cashCount",
            ),
            "trades" to setOf(
                "id",
                "instrumentId",
                "strategyId",
                "side",
                "quantity",
                "price",
                "executedAtEpochMillis",
                "status",
                "parentTradeId",
                "orderGroupId",
                "importBatchId",
                "note",
                "createdAtEpochMillis",
                "updatedAtEpochMillis",
            ),
            "trade_fees" to setOf("id", "tradeId", "kind", "amount", "note"),
            "cash_events" to setOf("id", "kind", "amount", "occurredAtEpochMillis", "importBatchId", "note"),
            "split_events" to setOf("id", "instrumentId", "exDateEpochDay", "newPerOld"),
            "position_snapshots" to setOf(
                "epochDay",
                "instrumentId",
                "quantity",
                "costBasis",
                "realizedPnl",
                "updatedAtEpochMillis",
            ),
            "watchlist" to setOf("instrumentId", "createdAt"),
        )
    }
}
