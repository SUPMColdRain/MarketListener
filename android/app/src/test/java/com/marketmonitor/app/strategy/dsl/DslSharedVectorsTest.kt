package com.marketmonitor.app.strategy.dsl

import com.fasterxml.jackson.databind.ObjectMapper
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs
import kotlin.math.max

class DslSharedVectorsTest {
    private val mapper = ObjectMapper()

    @Test
    fun sharedVectorsMatchDesktopExpectedResults() {
        val root = mapper.readTree(resource("dsl/vectors.json"))
        val vectors = root["vectors"]
        assertTrue(vectors.isArray && vectors.size() > 0)
        vectors.forEach { vector ->
            val id = vector["id"].asText()
            val program = DslProgram.parse(vector["strategy"].toString(), mapper)
            val series = mutableMapOf<String, List<Double>>()
            vector["series"].fields().forEach { (name, values) ->
                series[name] = values.map { it.asDouble() }
            }
            val parameters = mutableMapOf<String, Any>()
            vector["parameters"].fields().forEach { (name, value) ->
                parameters[name] = if (value.isIntegralNumber) value.asInt() else value.asDouble()
            }
            val expectedNodes = vector["expected"]["node_values"]
            val result = DslInterpreter().evaluate(
                program,
                series,
                parameters,
                outputNodes = expectedNodes.fieldNames().asSequence().toSet(),
            )

            val expectedIndices = vector["expected"]["signal_indices"].map { it.asInt() }
            assertEquals("$id signal indices", expectedIndices, result.signalIndices)
            val tolerance =
                if (vector["expected"].has("numeric_tolerance")) vector["expected"]["numeric_tolerance"].asDouble()
                else 1e-9
            expectedNodes.fieldNames().forEach { nodeId ->
                val expectedValues = expectedNodes[nodeId]
                val actualValues = result.nodeValues.getValue(nodeId)
                assertEquals("$id $nodeId length", expectedValues.size(), actualValues.size)
                for (index in 0 until expectedValues.size()) {
                    val expected = expectedValues[index]
                    val actual = actualValues[index]
                    if (expected.isNull) {
                        assertNull("$id $nodeId[$index] expected null", actual)
                    } else {
                        assertTrue("$id $nodeId[$index] expected number", actual is Number)
                        val a = (actual as Number).toDouble()
                        val b = expected.asDouble()
                        assertTrue(
                            "$id $nodeId[$index] $a vs $b exceeds tolerance $tolerance",
                            abs(a - b) <= tolerance * max(1.0, max(abs(a), abs(b))),
                        )
                    }
                }
            }
        }
    }

    private fun resource(name: String): String = javaClass.classLoader
        ?.getResourceAsStream(name)
        ?.bufferedReader()
        ?.use { it.readText() }
        ?: error("Missing test resource: $name")
}
