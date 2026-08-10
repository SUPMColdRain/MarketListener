package com.marketmonitor.app.strategy.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.marketmonitor.app.data.ImportedMarketData
import com.marketmonitor.app.strategy.dsl.DslProgram
import com.marketmonitor.app.ui.theme.MarketTheme

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
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = MarketTheme.dimensions.spacingMedium)
            .padding(vertical = MarketTheme.dimensions.spacingSmall),
        verticalArrangement = Arrangement.spacedBy(MarketTheme.dimensions.spacingSmall),
    ) {
        if (program == null) {
            Text("内置策略解析失败", style = MarketTheme.typography.bodySmall, color = MarketTheme.colors.error)
            return@Column
        }
        Text(
            text = "策略 ${program.strategyId} · v${program.strategyVersion} · DSL v${DslProgram.SCHEMA_VERSION}",
            style = MarketTheme.typography.labelMedium,
            color = MarketTheme.colorScheme.onSurfaceVariant,
        )
        Text("参数", style = MarketTheme.typography.labelLarge, color = MarketTheme.colorScheme.onSurfaceVariant)
        program.parameters.forEach { (name, definition) ->
            val type = definition["type"].asText()
            val minimum = definition.get("minimum")?.asDouble()
            val maximum = definition.get("maximum")?.asDouble()
            val current = parameterValues[name] ?: program.parameterDefaults()[name] ?: 0
            when (type) {
                "boolean" -> {
                    val checked = current as? Boolean ?: false
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = MarketTheme.dimensions.spacingSmall),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(name, style = MarketTheme.typography.bodyMedium)
                        Switch(
                            checked = checked,
                            onCheckedChange = { parameterValues[name] = it },
                        )
                    }
                    HorizontalDivider(color = MarketTheme.colorScheme.outlineVariant)
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
                        modifier = Modifier.fillMaxWidth(),
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
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(if (closeSeries.isEmpty()) "无行情数据，无法运行" else "运行策略")
        }
        errorMessage?.let {
            Text(
                text = "参数错误：$it",
                style = MarketTheme.typography.bodySmall,
                color = MarketTheme.colors.error,
            )
        }
        latestRun?.let { run ->
            Text("最近运行", style = MarketTheme.typography.labelLarge, color = MarketTheme.colorScheme.onSurfaceVariant)
            RunResultRow(run)
        }
        Text(
            text = "运行历史（${viewModel.history.size}）",
            style = MarketTheme.typography.labelLarge,
            color = MarketTheme.colorScheme.onSurfaceVariant,
        )
        if (viewModel.history.isEmpty()) {
            Text(
                text = "暂无运行记录",
                style = MarketTheme.typography.bodySmall,
                color = MarketTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(vertical = MarketTheme.dimensions.spacingMedium),
            )
        } else {
            viewModel.history.take(10).forEach { run -> RunResultRow(run) }
        }
    }
}

@Composable
private fun RunResultRow(run: StrategyRunRecord) {
    val statusColor = if (run.status == "PASS") MarketTheme.colors.priceUp else MarketTheme.colors.error
    Column(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = MarketTheme.dimensions.spacingSmall),
            horizontalArrangement = Arrangement.spacedBy(MarketTheme.dimensions.spacingSmall),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .background(statusColor, CircleShape),
            )
            Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(
                    text = "状态：${run.status}",
                    style = MarketTheme.typography.labelMedium,
                    color = statusColor,
                )
                if (run.status == "PASS") {
                    Text(
                        text = "信号：${run.signalLabel}",
                        style = MarketTheme.typography.bodySmall,
                        color = MarketTheme.colorScheme.onSurface,
                    )
                    Text(
                        text = "触发条件：${run.signalReason}",
                        style = MarketTheme.typography.bodySmall,
                        color = MarketTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        text = "信号位置：${run.signalIndices.joinToString(", ").ifEmpty { "无" }}",
                        style = MarketTheme.typography.bodySmall,
                        color = MarketTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        text = "风险标签：${run.riskTags.joinToString("、").ifEmpty { "无" }}",
                        style = MarketTheme.typography.bodySmall,
                        color = MarketTheme.colorScheme.onSurfaceVariant,
                    )
                } else {
                    Text(
                        text = "错误：${run.error ?: "未知"}",
                        style = MarketTheme.typography.bodySmall,
                        color = MarketTheme.colors.error,
                    )
                }
            }
        }
        HorizontalDivider(color = MarketTheme.colorScheme.outlineVariant)
    }
}
