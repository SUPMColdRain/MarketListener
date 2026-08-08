package com.marketmonitor.app.strategy.dsl

import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.ln
import kotlin.math.log10
import kotlin.math.pow
import kotlin.math.round
import kotlin.math.sqrt

/**
 * Kotlin whitelist interpreter for Strategy DSL v1. It receives only validated
 * [DslProgram] instances, evaluates node DAGs over aligned series and enforces
 * timeout, operation budget and cancellation exactly like the desktop
 * reference interpreter.
 */
class DslInterpreter {
    data class Result(
        val signals: List<Boolean>,
        val signalIndices: List<Int>,
        val nodeValues: Map<String, List<Any?>>,
        val parameters: Map<String, Any>,
        val ops: Long,
    )

    fun evaluate(
        program: DslProgram,
        series: Map<String, List<Double>>,
        parameters: Map<String, Any>? = null,
        timeoutMs: Long = 2_000,
        maxOps: Long = 500_000,
        isCancelled: () -> Boolean = { false },
        outputNodes: Set<String> = emptySet(),
    ): Result {
        for (input in program.inputs) {
            if (input !in series) throw DslException(DslErrorKind.NO_DATA, "missing input series $input")
        }
        val lengths = program.inputs.map { series.getValue(it).size }.toSet()
        if (lengths.size != 1) throw DslException(DslErrorKind.NO_DATA, "input series lengths differ")
        val count = lengths.first()
        if (count == 0) throw DslException(DslErrorKind.NO_DATA, "input series are empty")

        val resolved = resolveParameters(program, parameters)
        val evaluator = Evaluator(
            program = program,
            series = series,
            parameters = resolved,
            timeoutMs = timeoutMs,
            maxOps = maxOps,
            isCancelled = isCancelled,
            outputNodes = outputNodes,
            count = count,
        )
        return evaluator.run()
    }

    private fun resolveParameters(program: DslProgram, provided: Map<String, Any>?): Map<String, Any> {
        val merged = program.parameterDefaults().toMutableMap()
        provided?.forEach { (name, value) ->
            if (name !in program.parameters) throw DslException(DslErrorKind.PARAMETER, "unknown parameter $name")
            merged[name] = value
        }
        val resolved = HashMap<String, Any>()
        for ((name, definition) in program.parameters) {
            val value = merged.getValue(name)
            val type = definition["type"].asText()
            val normalized: Any = when (type) {
                "boolean" -> {
                    if (value !is Boolean) throw DslException(DslErrorKind.PARAMETER, "parameter $name must be boolean")
                    value
                }
                "integer" -> {
                    val number = numericValue(value, name) ?: throw DslException(DslErrorKind.PARAMETER, "parameter $name must be an integer")
                    if (number % 1.0 != 0.0) throw DslException(DslErrorKind.PARAMETER, "parameter $name must be an integer")
                    number.toInt()
                }
                else -> {
                    numericValue(value, name) ?: throw DslException(DslErrorKind.PARAMETER, "parameter $name must be a number")
                }
            }
            definition.get("minimum")?.asDouble()?.let { minimum ->
                if ((normalized as Number).toDouble() < minimum) {
                    throw DslException(DslErrorKind.PARAMETER, "parameter $name below minimum $minimum")
                }
            }
            definition.get("maximum")?.asDouble()?.let { maximum ->
                if ((normalized as Number).toDouble() > maximum) {
                    throw DslException(DslErrorKind.PARAMETER, "parameter $name above maximum $maximum")
                }
            }
            resolved[name] = normalized
        }
        return resolved
    }

    private fun numericValue(value: Any, name: String): Double? = when (value) {
        is Double -> value
        is Int -> value.toDouble()
        is Long -> value.toDouble()
        is Float -> value.toDouble()
        else -> {
            throw DslException(DslErrorKind.PARAMETER, "parameter $name must be a number")
        }
    }

    private inner class Evaluator(
        val program: DslProgram,
        val series: Map<String, List<Double>>,
        val parameters: Map<String, Any>,
        val timeoutMs: Long,
        val maxOps: Long,
        val isCancelled: () -> Boolean,
        val outputNodes: Set<String>,
        val count: Int,
    ) {
        private val values = HashMap<String, List<Any?>>()
        private var ops = 0L
        private val deadlineNanos = System.nanoTime() + timeoutMs * 1_000_000L

        fun run(): Result {
            val order = topologicalOrder()
            for (nodeId in order) {
                checkLimits()
                values[nodeId] = evaluateNode(program.nodes.getValue(nodeId))
            }
            val signalValues = values.getValue(program.signal.node)
            val signals = signalValues.map { it as? Boolean ?: false }
            val indices = signals.mapIndexedNotNull { index, value -> if (value) index else null }
            val captured = outputNodes.associateWith { values.getValue(it) }
            return Result(signals, indices, captured, parameters, ops)
        }

        private fun checkLimits() {
            if (isCancelled()) throw DslException(DslErrorKind.CANCELLED, "strategy evaluation cancelled")
            if (System.nanoTime() > deadlineNanos) {
                throw DslException(DslErrorKind.TIMEOUT, "strategy evaluation exceeded ${timeoutMs}ms")
            }
        }

        private fun bump(amount: Long = 1) {
            ops += amount
            if (ops > maxOps) throw DslException(DslErrorKind.LIMIT, "strategy exceeded operation budget $maxOps")
        }

        private fun evaluateNode(node: com.fasterxml.jackson.databind.JsonNode): List<Any?> {
            val kind = node["type"].asText()
            return when (kind) {
                "series" -> series.getValue(node["input"].asText()).map { it as Any? }
                "value" -> List(count) { node["value"].let { if (it.isNumber) it.asDouble() else it.asBoolean() } }
                "parameter" -> {
                    val value = parameters.getValue(node["name"].asText())
                    List(count) { value }
                }
                in NUMERIC_BINARY -> binaryNumeric(kind, node)
                in NUMERIC_UNARY -> unaryNumeric(kind, node)
                in COMPARISON_TYPES -> comparison(kind, node)
                in BOOLEAN_BINARY -> boolean(kind, node)
                "not" -> values.getValue(node["operand"].asText()).map { !asBoolean(it, node["operand"].asText()) }
                "ifelse" -> ifelse(node)
                in ROLLING_TYPES -> rolling(kind, node)
                "lag" -> lag(node)
                "crosses_above", "crosses_below" -> crosses(kind, node)
                else -> throw DslException(DslErrorKind.UNKNOWN_NODE, "unknown node type $kind")
            }
        }

        private fun binaryNumeric(kind: String, node: com.fasterxml.jackson.databind.JsonNode): List<Any?> {
            val left = values.getValue(node["left"].asText())
            val right = values.getValue(node["right"].asText())
            return List(count) { index ->
                if (index % BATCH == 0) checkLimits()
                bump()
                val a = left[index] as? Double
                val b = right[index] as? Double
                if (a == null || b == null) null else binaryNumber(node["left"].asText(), kind, a, b)
            }
        }

        private fun unaryNumeric(kind: String, node: com.fasterxml.jackson.databind.JsonNode): List<Any?> {
            val operand = values.getValue(node["operand"].asText())
            return List(count) { index ->
                if (index % BATCH == 0) checkLimits()
                bump()
                val value = operand[index] as? Double
                if (value == null) null else unaryNumber(node["operand"].asText(), kind, value)
            }
        }

        private fun comparison(kind: String, node: com.fasterxml.jackson.databind.JsonNode): List<Any?> {
            val left = values.getValue(node["left"].asText())
            val right = values.getValue(node["right"].asText())
            return List(count) { index ->
                if (index % BATCH == 0) checkLimits()
                bump()
                val a = left[index] as? Double
                val b = right[index] as? Double
                if (a == null || b == null) false else compare(kind, a, b)
            }
        }

        private fun boolean(kind: String, node: com.fasterxml.jackson.databind.JsonNode): List<Any?> {
            val left = values.getValue(node["left"].asText())
            val right = values.getValue(node["right"].asText())
            return List(count) { index ->
                if (index % BATCH == 0) checkLimits()
                bump()
                val a = asBoolean(left[index], node["left"].asText())
                val b = asBoolean(right[index], node["right"].asText())
                if (kind == "and") a && b else a || b
            }
        }

        private fun ifelse(node: com.fasterxml.jackson.databind.JsonNode): List<Any?> {
            val condition = values.getValue(node["condition"].asText())
            val thenValues = values.getValue(node["then"].asText())
            val elseValues = values.getValue(node["else"].asText())
            return List(count) { index ->
                if (index % BATCH == 0) checkLimits()
                bump()
                if (asBoolean(condition[index], node["condition"].asText())) thenValues[index] else elseValues[index]
            }
        }

        private fun rolling(kind: String, node: com.fasterxml.jackson.databind.JsonNode): List<Any?> {
            val operand = values.getValue(node["operand"].asText())
            val window = windowOf(node)
            if (kind == "ema") return ema(operand, window)
            val result = ArrayList<Any?>(count)
            for (index in 0 until count) {
                if (index % BATCH == 0) checkLimits()
                bump(minOf(window.toLong(), index + 1L))
                if (kind == "roc") {
                    if (index < window) {
                        result += null
                        continue
                    }
                    val previous = operand[index - window] as? Double
                    val current = operand[index] as? Double
                    if (previous == null || current == null || previous == 0.0) {
                        result += null
                    } else {
                        result += (current - previous) / previous
                    }
                    continue
                }
                if (index < window - 1) {
                    result += null
                    continue
                }
                val windowValues = operand.subList(index - window + 1, index + 1)
                if (windowValues.any { it !is Double }) {
                    result += null
                    continue
                }
                val numbers = windowValues.map { it as Double }
                result += rollingValue(kind, numbers, window)
            }
            return result
        }

        private fun ema(operand: List<Any?>, window: Int): List<Any?> {
            val result = ArrayList<Any?>(count)
            val alpha = 2.0 / (window + 1)
            var previous: Double? = null
            for (index in 0 until count) {
                if (index % BATCH == 0) checkLimits()
                bump()
                if (index < window - 1) {
                    result += null
                    continue
                }
                if (index == window - 1) {
                    val seedValues = operand.subList(0, window)
                    previous = if (seedValues.any { it !is Double }) null else seedValues.sumOf { it as Double } / window
                    result += previous
                    continue
                }
                val value = operand[index] as? Double
                if (value == null || previous == null) {
                    previous = null
                    result += null
                    continue
                }
                previous = alpha * value + (1.0 - alpha) * previous
                result += previous
            }
            return result
        }

        private fun rollingValue(kind: String, values: List<Double>, window: Int): Double = when (kind) {
            "sma" -> values.sum() / window
            "sum" -> values.sum()
            "rolling_max" -> values.max()
            "rolling_min" -> values.min()
            "stddev" -> {
                val mean = values.sum() / window
                sqrt(values.sumOf { (it - mean) * (it - mean) } / window)
            }
            else -> throw DslException(DslErrorKind.UNKNOWN_NODE, "unsupported rolling node $kind")
        }

        private fun windowOf(node: com.fasterxml.jackson.databind.JsonNode): Int {
            val window = node["window"]
            if (window.isInt) return window.asInt()
            val resolved = values.getValue(window.asText()).firstOrNull()
            val number = resolved as? Number ?: throw DslException(DslErrorKind.TYPE, "window node did not resolve to a number")
            val value = number.toDouble()
            if (value < 1.0 || value % 1.0 != 0.0) {
                throw DslException(DslErrorKind.PARAMETER, "window parameter resolved to invalid value $value")
            }
            return value.toInt()
        }

        private fun lag(node: com.fasterxml.jackson.databind.JsonNode): List<Any?> {
            val operand = values.getValue(node["operand"].asText())
            val offset = node["offset"].asInt()
            return List(count) { index -> if (index < offset) null else operand[index - offset] }
        }

        private fun crosses(kind: String, node: com.fasterxml.jackson.databind.JsonNode): List<Any?> {
            val fast = values.getValue(node["fast"].asText())
            val slow = values.getValue(node["slow"].asText())
            return List(count) { index ->
                if (index % BATCH == 0) checkLimits()
                bump()
                if (index == 0) return@List false
                val fastNow = fast[index] as? Double
                val slowNow = slow[index] as? Double
                val fastPrev = fast[index - 1] as? Double
                val slowPrev = slow[index - 1] as? Double
                if (fastNow == null || slowNow == null || fastPrev == null || slowPrev == null) false
                else if (kind == "crosses_above") fastPrev <= slowPrev && fastNow > slowNow
                else fastPrev >= slowPrev && fastNow < slowNow
            }
        }

        private fun asBoolean(value: Any?, nodeId: String): Boolean {
            if (value == null) return false
            if (value !is Boolean) throw DslException(DslErrorKind.TYPE, "node $nodeId expected boolean")
            return value
        }

        private fun binaryNumber(nodeId: String, kind: String, left: Double, right: Double): Double = try {
            when (kind) {
                "add" -> left + right
                "subtract" -> left - right
                "multiply" -> left * right
                "divide" -> {
                    if (right == 0.0) throw ArithmeticException("division by zero")
                    left / right
                }
                "modulo" -> {
                    if (right == 0.0) throw ArithmeticException("modulo by zero")
                    left % right
                }
                "pow" -> left.pow(right)
                "max" -> maxOf(left, right)
                "min" -> minOf(left, right)
                else -> throw DslException(DslErrorKind.UNKNOWN_NODE, "unknown binary node $kind")
            }
        } catch (error: ArithmeticException) {
            throw DslException(DslErrorKind.NUMERIC, "numeric error in node $nodeId ($kind): ${error.message}")
        }

        private fun unaryNumber(nodeId: String, kind: String, value: Double): Double = try {
            when (kind) {
                "negate" -> -value
                "abs" -> abs(value)
                "sqrt" -> sqrt(value)
                "ln" -> ln(value)
                "log10" -> log10(value)
                "floor" -> floor(value)
                "ceil" -> ceil(value)
                "round" -> round(value)
                else -> throw DslException(DslErrorKind.UNKNOWN_NODE, "unknown unary node $kind")
            }
        } catch (error: IllegalArgumentException) {
            throw DslException(DslErrorKind.NUMERIC, "numeric error in node $nodeId ($kind): ${error.message}")
        }

        private fun compare(kind: String, left: Double, right: Double): Boolean = when (kind) {
            "eq" -> left == right
            "neq" -> left != right
            "lt" -> left < right
            "lte" -> left <= right
            "gt" -> left > right
            else -> left >= right
        }

        private fun topologicalOrder(): List<String> {
            val visited = HashSet<String>()
            val order = ArrayList<String>()
            fun visit(nodeId: String, stack: MutableSet<String>) {
                if (nodeId in visited) return
                if (!stack.add(nodeId)) throw DslException(DslErrorKind.CYCLE, "node cycle detected through $nodeId")
                for (ref in refsOf(program.nodes.getValue(nodeId))) visit(ref, stack)
                stack.remove(nodeId)
                visited += nodeId
                order += nodeId
            }
            for (nodeId in program.nodes.keys) visit(nodeId, HashSet())
            return order
        }

        private fun refsOf(node: com.fasterxml.jackson.databind.JsonNode): List<String> {
            val refs = mutableListOf<String>()
            for (key in listOf("left", "right", "operand", "fast", "slow", "condition", "then", "else")) {
                node.get(key)?.takeIf { it.isTextual }?.let { refs += it.asText() }
            }
            node.get("window")?.takeIf { it.isTextual }?.let { refs += it.asText() }
            return refs
        }

    }

    private companion object {
        const val BATCH = 4096
        val NUMERIC_BINARY = setOf("add", "subtract", "multiply", "divide", "modulo", "pow", "max", "min")
        val NUMERIC_UNARY = setOf("negate", "abs", "sqrt", "ln", "log10", "floor", "ceil", "round")
        val COMPARISON_TYPES = setOf("eq", "neq", "lt", "lte", "gt", "gte")
        val BOOLEAN_BINARY = setOf("and", "or")
        val ROLLING_TYPES = setOf("sma", "ema", "sum", "stddev", "rolling_max", "rolling_min", "roc")
    }
}
