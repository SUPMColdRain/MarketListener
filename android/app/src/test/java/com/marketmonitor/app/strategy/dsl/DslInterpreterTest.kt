package com.marketmonitor.app.strategy.dsl

import com.fasterxml.jackson.databind.ObjectMapper
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

class DslInterpreterTest {
    private val mapper = ObjectMapper()

    private val validProgram =
        """
        {
          "schema_version": 1,
          "strategy_id": "jvm_smoke",
          "strategy_version": "1.0.0",
          "inputs": ["close"],
          "parameters": {},
          "nodes": {
            "close_series": {"type": "series", "input": "close"},
            "hundred": {"type": "value", "value": 100},
            "above": {"type": "gt", "left": "close_series", "right": "hundred"}
          },
          "signal": {"node": "above", "label": "above 100", "reason": "smoke", "risk_tags": []}
        }
        """.trimIndent()

    @Test
    fun validProgramEvaluatesSignalsWithoutCrashing() {
        val program = DslProgram.parse(validProgram, mapper)
        val result = DslInterpreter().evaluate(
            program,
            mapOf("close" to listOf(90.0, 110.0)),
        )

        assertEquals(listOf(1), result.signalIndices)
        assertEquals(listOf(false, true), result.signals)
    }

    @Test
    fun unknownNodeTypeIsSchemaError() {
        val document = validProgram.replace("\"gt\"", "\"eval\"")
        assertKind(DslErrorKind.SCHEMA) {
            DslProgram.parse(document, mapper)
        }
    }

    @Test
    fun arbitraryCodeNodeIsRejectedBeforeEvaluation() {
        val document =
            """
            {
              "schema_version": 1,
              "strategy_id": "jvm_evil",
              "strategy_version": "1.0.0",
              "inputs": ["close"],
              "parameters": {},
              "nodes": {
                "close_series": {"type": "series", "input": "close"},
                "payload": {"type": "http_request", "url": "https://example.com"}
              },
              "signal": {"node": "close_series", "label": "x", "reason": "y", "risk_tags": []}
            }
            """.trimIndent()
        assertKind(DslErrorKind.SCHEMA) {
            DslProgram.parse(document, mapper)
        }
    }

    @Test
    fun missingInputSeriesIsNoData() {
        val program = DslProgram.parse(validProgram, mapper)
        assertKind(DslErrorKind.NO_DATA) {
            DslInterpreter().evaluate(program, mapOf())
        }
    }

    @Test
    fun emptySeriesIsNoData() {
        val program = DslProgram.parse(validProgram, mapper)
        assertKind(DslErrorKind.NO_DATA) {
            DslInterpreter().evaluate(program, mapOf("close" to emptyList()))
        }
    }

    @Test
    fun divisionByZeroIsNumericError() {
        val document =
            """
            {
              "schema_version": 1,
              "strategy_id": "jvm_div0",
              "strategy_version": "1.0.0",
              "inputs": ["close"],
              "parameters": {},
              "nodes": {
                "close_series": {"type": "series", "input": "close"},
                "zero": {"type": "value", "value": 0},
                "quotient": {"type": "divide", "left": "close_series", "right": "zero"},
                "positive": {"type": "gt", "left": "quotient", "right": "zero"}
              },
              "signal": {"node": "positive", "label": "q", "reason": "r", "risk_tags": []}
            }
            """.trimIndent()
        val program = DslProgram.parse(document, mapper)
        assertKind(DslErrorKind.NUMERIC) {
            DslInterpreter().evaluate(program, mapOf("close" to listOf(1.0)))
        }
    }

    @Test
    fun timeoutRaisesTimeout() {
        val program = DslProgram.parse(validProgram, mapper)
        assertKind(DslErrorKind.TIMEOUT) {
            DslInterpreter().evaluate(program, mapOf("close" to listOf(90.0, 110.0)), timeoutMs = 0)
        }
    }

    @Test
    fun cancellationRaisesCancelled() {
        val program = DslProgram.parse(validProgram, mapper)
        assertKind(DslErrorKind.CANCELLED) {
            DslInterpreter().evaluate(program, mapOf("close" to listOf(90.0, 110.0)), isCancelled = { true })
        }
    }

    @Test
    fun operationBudgetExceededRaisesLimit() {
        val program = DslProgram.parse(validProgram, mapper)
        assertKind(DslErrorKind.LIMIT) {
            DslInterpreter().evaluate(program, mapOf("close" to listOf(90.0, 110.0)), maxOps = 0)
        }
    }

    @Test
    fun nonBooleanSignalNodeIsTypeError() {
        val document =
            """
            {
              "schema_version": 1,
              "strategy_id": "jvm_type",
              "strategy_version": "1.0.0",
              "inputs": ["close"],
              "parameters": {},
              "nodes": {
                "close_series": {"type": "series", "input": "close"}
              },
              "signal": {"node": "close_series", "label": "x", "reason": "y", "risk_tags": []}
            }
            """.trimIndent()
        assertKind(DslErrorKind.TYPE) {
            DslProgram.parse(document, mapper)
        }
    }

    private inline fun assertKind(expected: DslErrorKind, block: () -> Unit) {
        try {
            block()
            fail("expected DslException($expected)")
        } catch (error: DslException) {
            assertEquals(expected, error.kind)
        }
    }
}
