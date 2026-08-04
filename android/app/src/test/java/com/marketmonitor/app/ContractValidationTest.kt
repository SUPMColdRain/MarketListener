package com.marketmonitor.app

import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.ObjectMapper
import com.networknt.schema.JsonSchemaFactory
import com.networknt.schema.SpecVersion
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.OffsetDateTime

class ContractValidationTest {
    private val mapper = ObjectMapper()

    @Test
    fun sharedContractFixturesAreAcceptedOrRejectedAsDeclared() {
        val cases = mapper.readTree(resource("contracts/cases.json"))
        cases.forEach { case ->
            val document = mapper.readTree(resource("contracts/${case["fixture"].asText()}"))
            val errors = schema(case["schema"].asText())
                .validate(document)
                .map { it.message }
                .toMutableList()
            if (errors.isEmpty() && case["schema"].asText() == "bar.schema.json") {
                barSemanticError(document)?.let(errors::add)
            }

            if (case["valid"].asBoolean()) {
                assertTrue("${case["id"].asText()}: $errors", errors.isEmpty())
            } else {
                assertFalse("${case["id"].asText()} should fail", errors.isEmpty())
            }
        }
    }

    private fun schema(name: String) = JsonSchemaFactory
        .getInstance(SpecVersion.VersionFlag.V202012)
        .getSchema(mapper.readTree(resource(name)))

    private fun resource(name: String): String = javaClass.classLoader
        ?.getResourceAsStream(name)
        ?.bufferedReader()
        ?.use { it.readText() }
        ?: error("Missing test resource: $name")

    private fun barSemanticError(bar: JsonNode): String? {
        if (!bar.has("low") || !bar.has("high") || !bar.has("open") || !bar.has("close")) return null
        val low = bar["low"].asDouble()
        val high = bar["high"].asDouble()
        val open = bar["open"].asDouble()
        val close = bar["close"].asDouble()
        return when {
            low > minOf(open, close) || high < maxOf(open, close) || low > high ->
                "bar low/high must bound open and close"
            bar.has("bar_open_time") && bar.has("bar_close_time") &&
                !OffsetDateTime.parse(bar["bar_open_time"].asText()).isBefore(
                    OffsetDateTime.parse(bar["bar_close_time"].asText()),
                ) ->
                "bar_open_time must be before bar_close_time"
            else -> null
        }
    }
}
