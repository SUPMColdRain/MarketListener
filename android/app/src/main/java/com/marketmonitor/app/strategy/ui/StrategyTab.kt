package com.marketmonitor.app.strategy.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.marketmonitor.app.data.ImportedMarketData
import com.marketmonitor.app.strategy.dsl.DslProgram

private val SAMPLE_STRATEGY = """
{
  "schema_version": 1,
  "strategy_id": "app_ma_cross",
  "strategy_version": "1.0.0",
  "inputs": ["close"],
  "parameters": {
    "fast_window": {"type": "integer", "minimum": 2, "maximum": 10, "default": 2},
    "slow_window": {"type": "integer", "minimum": 3, "maximum": 20, "default": 3}
  },
  "nodes": {
    "close_series": {"type": "series", "input": "close"},
    "fast_param": {"type": "parameter", "name": "fast_window"},
    "slow_param": {"type": "parameter", "name": "slow_window"},
    "fast_sma": {"type": "sma", "operand": "close_series", "window": "fast_param"},
    "slow_sma": {"type": "sma", "operand": "close_series", "window": "slow_param"},
    "golden_cross": {"type": "crosses_above", "fast": "fast_sma", "slow": "slow_sma"}
  },
  "signal": {
    "node": "golden_cross",
    "label": "快线上穿慢线",
    "reason": "短期均线由下向上穿越长期均线",
    "risk_tags": ["趋势跟踪", "样本外需复核"]
  }
}
""".trimIndent()

@Composable
fun StrategyTab(
    viewModel: StrategyViewModel,
    marketData: ImportedMarketData?,
) {
    val programJson = remember { SAMPLE_STRATEGY }
    val program = remember { runCatching { DslProgram.parse(programJson) }.getOrNull() }
    val parameterValues = remember { mutableStateMapOf<String, Any>() }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var latestRun by remember { mutableStateOf<StrategyRunRecord?>(null) }
    val closeSeries = remember(marketData?.packageId) {
        marketData?.instruments?.firstOrNull()?.candlesByPeriod?.get("1d")?.map { it.close } ?: emptyList()
    }

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("策略（声明式 DSL v1）", style = MaterialTheme.typography.titleLarge)
        if (program == null) {
            Text("内置策略解析失败", color = MaterialTheme.colorScheme.error)
            return@Column
        }
        Text("策略：${program.strategyId} v${program.strategyVersion}", style = MaterialTheme.typography.labelLarge)
        program.parameters.forEach { (name, definition) ->
            val type = definition["type"].asText()
            val minimum = definition.get("minimum")?.asDouble()
            val maximum = definition.get("maximum")?.asDouble()
            val current = parameterValues[name] ?: program.parameterDefaults()[name] ?: 0
            when (type) {
                "boolean" -> {
                    val checked = current as? Boolean ?: false
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(name)
                        Switch(
                            checked = checked,
                            onCheckedChange = { parameterValues[name] = it },
                        )
                    }
                }
                else -> {
                    var text by remember(name) { mutableStateOf(current.toString()) }
                    OutlinedTextField(
                        value = text,
                        onValueChange = { newValue ->
                            text = newValue
                            newValue.toDoubleOrNull()?.let { value ->
                                if (type == "integer") {
                                    if (value % 1.0 == 0.0) parameterValues[name] = value.toInt()
                                } else {
                                    parameterValues[name] = value
                                }
                            }
                        },
                        label = { Text("$name（${minimum ?: "-∞"} ~ ${maximum ?: "+∞"}）") },
                        singleLine = true,
                    )
                }
            }
        }
        Button(
            enabled = closeSeries.isNotEmpty(),
            onClick = {
                errorMessage = viewModel.validate(programJson, parameterValues.toMap())
                if (errorMessage == null) {
                    latestRun = viewModel.run(programJson, mapOf("close" to closeSeries), parameterValues.toMap())
                }
            },
        ) {
            Text(if (closeSeries.isEmpty()) "无行情数据，无法运行" else "运行策略")
        }
        errorMessage?.let { Text("参数错误：$it", color = MaterialTheme.colorScheme.error) }
        latestRun?.let { run -> RunExplanationCard(run) }
        Text("运行历史（${viewModel.history.size}）", style = MaterialTheme.typography.titleMedium)
        viewModel.history.take(10).forEach { run -> RunExplanationCard(run) }
    }
}

@Composable
private fun RunExplanationCard(run: StrategyRunRecord) {
    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text("状态：${run.status}", style = MaterialTheme.typography.labelLarge)
            if (run.status == "PASS") {
                Text("信号：${run.signalLabel}")
                Text("触发条件：${run.signalReason}")
                Text("信号位置：${run.signalIndices.joinToString(", ").ifEmpty { "无" }}")
                Text("风险标签：${run.riskTags.joinToString("、").ifEmpty { "无" }}")
            } else {
                Text("错误：${run.error ?: "未知"}", color = MaterialTheme.colorScheme.error)
            }
        }
    }
}
