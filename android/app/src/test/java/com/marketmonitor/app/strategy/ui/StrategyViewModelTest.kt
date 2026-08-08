package com.marketmonitor.app.strategy.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class StrategyViewModelTest {
    private val strategyJson = """
        {
          "schema_version": 1,
          "strategy_id": "test_ma_cross",
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
            "reason": "短期均线上穿长期均线",
            "risk_tags": ["趋势跟踪"]
          }
        }
    """.trimIndent()
    private val closes = listOf(10.0, 10.5, 10.2, 10.8, 11.2, 11.0, 10.6, 10.9, 11.5, 12.0)

    @Test
    fun validParametersRunPassesWithExplanationAndHistory() {
        val store = InMemoryStrategyHistoryStore()
        val viewModel = StrategyViewModel(store, clock = { 1_234L })

        val record = viewModel.run(strategyJson, mapOf("close" to closes), mapOf("fast_window" to 2, "slow_window" to 3))

        assertEquals("PASS", record.status)
        assertEquals(listOf(4, 8), record.signalIndices)
        assertEquals("快线上穿慢线", record.signalLabel)
        assertEquals("短期均线上穿长期均线", record.signalReason)
        assertEquals(listOf("趋势跟踪"), record.riskTags)
        assertEquals(1, viewModel.history.size)
        assertEquals(1, store.load().size)
    }

    @Test
    fun outOfBoundsParametersAreRejectedBeforeRunning() {
        val viewModel = StrategyViewModel(InMemoryStrategyHistoryStore())

        val error = viewModel.validate(strategyJson, mapOf("fast_window" to 1, "slow_window" to 3))

        assertTrue(error != null)
        assertEquals(0, viewModel.history.size)
    }

    @Test
    fun runtimeParameterErrorIsRecordedWithoutCrashing() {
        val viewModel = StrategyViewModel(InMemoryStrategyHistoryStore())

        val record = viewModel.run(
            strategyJson,
            mapOf("close" to closes),
            mapOf("fast_window" to 1, "slow_window" to 3),
        )

        assertEquals("FAILED", record.status)
        assertEquals(1, viewModel.history.size)
        assertTrue(record.error != null)
    }
}
