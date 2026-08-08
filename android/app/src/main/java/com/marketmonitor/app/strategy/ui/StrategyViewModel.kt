package com.marketmonitor.app.strategy.ui

import android.content.Context
import com.marketmonitor.app.strategy.dsl.DslException
import com.marketmonitor.app.strategy.dsl.DslInterpreter
import com.marketmonitor.app.strategy.dsl.DslProgram
import org.json.JSONArray
import org.json.JSONObject

data class StrategyRunRecord(
    val startedAtMillis: Long,
    val parameterValues: Map<String, Any>,
    val signalIndices: List<Int>,
    val signalLabel: String,
    val signalReason: String,
    val riskTags: List<String>,
    val status: String,
    val error: String? = null,
)

interface StrategyHistoryStore {
    fun load(): List<StrategyRunRecord>
    fun save(records: List<StrategyRunRecord>)
}

class InMemoryStrategyHistoryStore : StrategyHistoryStore {
    private var records: List<StrategyRunRecord> = emptyList()
    override fun load(): List<StrategyRunRecord> = records
    override fun save(items: List<StrategyRunRecord>) {
        records = items
    }
}

class PreferencesStrategyHistoryStore(context: Context) : StrategyHistoryStore {
    private val preferences = context.getSharedPreferences("strategy-runs", Context.MODE_PRIVATE)

    override fun load(): List<StrategyRunRecord> {
        val raw = preferences.getString("history", null) ?: return emptyList()
        return try {
            val array = JSONArray(raw)
            (0 until array.length()).map { index -> decode(array.getJSONObject(index)) }
        } catch (_: Exception) {
            emptyList()
        }
    }

    override fun save(records: List<StrategyRunRecord>) {
        val array = JSONArray()
        records.forEach { array.put(encode(it)) }
        preferences.edit().putString("history", array.toString()).apply()
    }

    private fun encode(record: StrategyRunRecord): JSONObject = JSONObject()
        .put("started_at", record.startedAtMillis)
        .put("parameters", JSONObject(record.parameterValues.mapValues { it.value.toString() }))
        .put("signal_indices", JSONArray(record.signalIndices))
        .put("label", record.signalLabel)
        .put("reason", record.signalReason)
        .put("risk_tags", JSONArray(record.riskTags))
        .put("status", record.status)
        .put("error", record.error ?: JSONObject.NULL)

    private fun decode(json: JSONObject): StrategyRunRecord = StrategyRunRecord(
        startedAtMillis = json.getLong("started_at"),
        parameterValues = emptyMap(),
        signalIndices = json.getJSONArray("signal_indices").let { array ->
            (0 until array.length()).map { array.getInt(it) }
        },
        signalLabel = json.getString("label"),
        signalReason = json.getString("reason"),
        riskTags = json.getJSONArray("risk_tags").let { array ->
            (0 until array.length()).map { array.getString(it) }
        },
        status = json.getString("status"),
        error = if (json.isNull("error")) null else json.getString("error"),
    )
}

class StrategyViewModel(
    private val historyStore: StrategyHistoryStore,
    private val clock: () -> Long = { System.currentTimeMillis() },
) {
    var history: List<StrategyRunRecord> = historyStore.load()
        private set

    fun validate(programJson: String, parameters: Map<String, Any>): String? {
        val program = try {
            DslProgram.parse(programJson)
        } catch (error: DslException) {
            return "${error.kind}: ${error.message}"
        }
        for ((name, definition) in program.parameters) {
            val value = parameters[name] ?: continue
            val type = definition["type"].asText()
            val number = when {
                value is Int -> value.toDouble()
                value is Double -> value
                value is Boolean && type == "boolean" -> continue
                else -> return "参数 $name 类型不匹配"
            }
            definition.get("minimum")?.asDouble()?.let { minimum ->
                if (number < minimum) return "参数 $name 低于最小值 $minimum"
            }
            definition.get("maximum")?.asDouble()?.let { maximum ->
                if (number > maximum) return "参数 $name 高于最大值 $maximum"
            }
            if (type == "integer" && number % 1.0 != 0.0) {
                return "参数 $name 必须为整数"
            }
        }
        return null
    }

    fun run(programJson: String, series: Map<String, List<Double>>, parameters: Map<String, Any>): StrategyRunRecord {
        val record = try {
            val program = DslProgram.parse(programJson)
            val result = DslInterpreter().evaluate(program, series, parameters)
            StrategyRunRecord(
                startedAtMillis = clock(),
                parameterValues = parameters,
                signalIndices = result.signalIndices,
                signalLabel = program.signal.label,
                signalReason = program.signal.reason,
                riskTags = program.signal.riskTags,
                status = "PASS",
            )
        } catch (error: DslException) {
            StrategyRunRecord(
                startedAtMillis = clock(),
                parameterValues = parameters,
                signalIndices = emptyList(),
                signalLabel = "",
                signalReason = "",
                riskTags = emptyList(),
                status = "FAILED",
                error = "${error.kind}: ${error.message}",
            )
        }
        history = listOf(record) + history
        historyStore.save(history)
        return record
    }
}
