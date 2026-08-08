package com.marketmonitor.app.strategy.dsl

import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.ObjectMapper

data class DslLimits(val maxNodes: Int, val maxDepth: Int)

data class DslSignal(
    val node: String,
    val label: String,
    val reason: String,
    val riskTags: List<String>,
)

/**
 * Validated Strategy DSL v1 document. Only whitelisted node types survive
 * parsing; arbitrary code, network access and file access have no node type
 * and are rejected as SCHEMA errors before any evaluation starts.
 */
class DslProgram private constructor(
    val raw: JsonNode,
    val strategyId: String,
    val strategyVersion: String,
    val inputs: List<String>,
    val parameters: Map<String, JsonNode>,
    val nodes: Map<String, JsonNode>,
    val nodeTypes: Map<String, String>,
    val signal: DslSignal,
    val limits: DslLimits,
) {
    fun parameterDefaults(): Map<String, Any> =
        parameters.mapValues { (_, definition) -> parameterValue(definition["type"].asText(), definition["default"]) }

    companion object {
        const val SCHEMA_VERSION = 1
        const val DEFAULT_MAX_NODES = 200
        const val DEFAULT_MAX_DEPTH = 32

        private val INPUT_FIELDS = setOf("open", "high", "low", "close", "volume", "amount")
        private val NODE_REF_KEYS = listOf("left", "right", "operand", "fast", "slow", "condition", "then", "else")
        private val ROLLING_TYPES = setOf("sma", "ema", "sum", "stddev", "rolling_max", "rolling_min", "roc")
        private val NUMERIC_BINARY = setOf("add", "subtract", "multiply", "divide", "modulo", "pow", "max", "min")
        private val NUMERIC_UNARY = setOf("negate", "abs", "sqrt", "ln", "log10", "floor", "ceil", "round")
        private val COMPARISON_TYPES = setOf("eq", "neq", "lt", "lte", "gt", "gte")
        private val BOOLEAN_BINARY = setOf("and", "or")
        private val ALLOWED_TYPES =
            NUMERIC_BINARY +
                NUMERIC_UNARY +
                COMPARISON_TYPES +
                BOOLEAN_BINARY +
                setOf("series", "value", "parameter", "not", "ifelse", "lag", "crosses_above", "crosses_below") +
                ROLLING_TYPES

        private val IDENTIFIER = Regex("^[A-Za-z_][A-Za-z0-9_]{0,63}$")
        private val STRATEGY_ID = Regex("^[a-z][a-z0-9_.-]{2,63}$")
        private val VERSION = Regex("^[0-9]+\\.[0-9]+\\.[0-9]+$")

        fun parse(json: String, mapper: ObjectMapper = ObjectMapper()): DslProgram {
            val root = try {
                mapper.readTree(json)
            } catch (error: Exception) {
                throw DslException(DslErrorKind.SCHEMA, "invalid JSON: ${error.message}")
            }
            return parse(root)
        }

        fun parse(root: JsonNode): DslProgram {
            requireObject(root, "document")
            if (!root.has("schema_version") || root["schema_version"].asInt() != SCHEMA_VERSION) {
                throw DslException(DslErrorKind.SCHEMA, "schema_version must be $SCHEMA_VERSION")
            }
            val strategyId = text(root, "strategy_id")
            if (!STRATEGY_ID.matches(strategyId)) throw DslException(DslErrorKind.SCHEMA, "invalid strategy_id")
            val strategyVersion = text(root, "strategy_version")
            if (!VERSION.matches(strategyVersion)) throw DslException(DslErrorKind.SCHEMA, "invalid strategy_version")

            val inputs = parseInputs(root)
            val parameters = parseParameters(root)
            val nodes = parseNodes(root)
            val limits = parseLimits(root)
            if (nodes.size > limits.maxNodes) {
                throw DslException(DslErrorKind.LIMIT, "node count ${nodes.size} exceeds max_nodes ${limits.maxNodes}")
            }

            val nodeTypes = inferNodeTypes(nodes, parameters, inputs.toSet())
            for (nodeId in nodes.keys) validateDepth(nodeId, nodes, limits, HashMap())
            for ((nodeId, node) in nodes) validateOperandKinds(nodeId, node, nodeTypes)
            for ((nodeId, node) in nodes) validateWindowRefs(nodeId, node, nodes, parameters)

            val signal = parseSignal(root, nodes, nodeTypes)
            return DslProgram(
                raw = root,
                strategyId = strategyId,
                strategyVersion = strategyVersion,
                inputs = inputs,
                parameters = parameters,
                nodes = nodes,
                nodeTypes = nodeTypes,
                signal = signal,
                limits = limits,
            )
        }

        private fun parseInputs(root: JsonNode): List<String> {
            if (!root.has("inputs") || !root["inputs"].isArray || root["inputs"].isEmpty) {
                throw DslException(DslErrorKind.SCHEMA, "inputs must be a non-empty array")
            }
            val inputs = mutableListOf<String>()
            val seen = mutableSetOf<String>()
            root["inputs"].forEach { item ->
                if (!item.isTextual || item.asText() !in INPUT_FIELDS) {
                    throw DslException(DslErrorKind.SCHEMA, "input must be one of $INPUT_FIELDS")
                }
                if (!seen.add(item.asText())) throw DslException(DslErrorKind.SCHEMA, "duplicate input ${item.asText()}")
                inputs += item.asText()
            }
            return inputs
        }

        private fun parseParameters(root: JsonNode): Map<String, JsonNode> {
            val parameters = root.get("parameters")
            if (parameters == null || !parameters.isObject) {
                throw DslException(DslErrorKind.SCHEMA, "parameters must be an object")
            }
            val result = linkedMapOf<String, JsonNode>()
            parameters.fields().forEach { (name, definition) ->
                if (!IDENTIFIER.matches(name)) throw DslException(DslErrorKind.SCHEMA, "invalid parameter name $name")
                requireObject(definition, "parameter $name")
                val type = definition.get("type")?.asText()
                if (type == null || type !in setOf("number", "integer", "boolean")) {
                    throw DslException(DslErrorKind.SCHEMA, "parameter $name has unsupported type")
                }
                if (!definition.has("default")) throw DslException(DslErrorKind.SCHEMA, "parameter $name needs a default")
                val default = definition["default"]
                val defaultMatches = when (type) {
                    "number" -> default.isNumber
                    "integer" -> default.isIntegralNumber
                    else -> default.isBoolean
                }
                if (!defaultMatches) throw DslException(DslErrorKind.SCHEMA, "parameter $name default type mismatch")
                for (bound in listOf("minimum", "maximum")) {
                    if (definition.has(bound) && (!definition[bound].isNumber || (type == "integer" && !definition[bound].isIntegralNumber))) {
                        throw DslException(DslErrorKind.SCHEMA, "parameter $name $bound must be a ${type}")
                    }
                }
                val minimum = definition.get("minimum")?.asDouble()
                val maximum = definition.get("maximum")?.asDouble()
                val value = (parameterValue(type, default) as? Number)?.toDouble() ?: 0.0
                if (minimum != null && value < minimum) {
                    throw DslException(DslErrorKind.PARAMETER, "parameter $name default below minimum")
                }
                if (maximum != null && value > maximum) {
                    throw DslException(DslErrorKind.PARAMETER, "parameter $name default above maximum")
                }
                result[name] = definition
            }
            if (result.size > 64) throw DslException(DslErrorKind.LIMIT, "too many parameters")
            return result
        }

        private fun parseNodes(root: JsonNode): Map<String, JsonNode> {
            val nodes = root.get("nodes")
            if (nodes == null || !nodes.isObject || nodes.isEmpty) {
                throw DslException(DslErrorKind.SCHEMA, "nodes must be a non-empty object")
            }
            val result = linkedMapOf<String, JsonNode>()
            nodes.fields().forEach { (name, node) ->
                if (!IDENTIFIER.matches(name)) throw DslException(DslErrorKind.SCHEMA, "invalid node name $name")
                requireObject(node, "node $name")
                val type = node.get("type")?.asText()
                if (type == null || type !in ALLOWED_TYPES) {
                    throw DslException(DslErrorKind.SCHEMA, "node $name uses disallowed type ${type ?: "<missing>"}")
                }
                validateNodeShape(name, type, node)
                result[name] = node
            }
            return result
        }

        private fun validateNodeShape(nodeId: String, type: String, node: JsonNode) {
            val allowed = when (type) {
                "series" -> setOf("type", "input")
                "value" -> setOf("type", "value")
                "parameter" -> setOf("type", "name")
                "not", "negate", "abs", "sqrt", "ln", "log10", "floor", "ceil", "round", "lag" -> setOf("type", "operand")
                "ifelse" -> setOf("type", "condition", "then", "else")
                in ROLLING_TYPES -> setOf("type", "operand", "window")
                "crosses_above", "crosses_below" -> setOf("type", "fast", "slow")
                else -> setOf("type", "left", "right")
            }
            val actual = node.fieldNames().asSequence().toSet()
            if (actual != allowed) {
                throw DslException(DslErrorKind.SCHEMA, "node $nodeId type $type has unexpected fields $actual")
            }
            when (type) {
                "series" -> {
                    val input = node.get("input")?.asText()
                    if (input !in INPUT_FIELDS) throw DslException(DslErrorKind.SCHEMA, "node $nodeId uses invalid input")
                }
                "value" -> if (!node["value"].isNumber && !node["value"].isBoolean) {
                    throw DslException(DslErrorKind.SCHEMA, "node $nodeId value must be number or boolean")
                }
                "parameter" -> if (!IDENTIFIER.matches(node["name"].asText())) {
                    throw DslException(DslErrorKind.SCHEMA, "node $nodeId has invalid parameter name")
                }
                in ROLLING_TYPES -> {
                    val window = node["window"]
                    val valid = window.isInt && window.asInt() >= 1 && window.asInt() <= 1000 ||
                        window.isTextual && IDENTIFIER.matches(window.asText())
                    if (!valid) throw DslException(DslErrorKind.SCHEMA, "node $nodeId has invalid window")
                }
                "lag" -> {
                    val offset = node["offset"]
                    if (!offset.isInt || offset.asInt() < 1 || offset.asInt() > 10000) {
                        throw DslException(DslErrorKind.SCHEMA, "node $nodeId has invalid lag offset")
                    }
                }
            }
        }

        private fun parseLimits(root: JsonNode): DslLimits {
            if (!root.has("limits")) return DslLimits(DEFAULT_MAX_NODES, DEFAULT_MAX_DEPTH)
            val limits = root["limits"]
            requireObject(limits, "limits")
            val maxNodes = limits.get("max_nodes")?.let {
                if (!it.isInt || it.asInt() < 1 || it.asInt() > 2000) {
                    throw DslException(DslErrorKind.SCHEMA, "invalid max_nodes")
                }
                it.asInt()
            } ?: DEFAULT_MAX_NODES
            val maxDepth = limits.get("max_depth")?.let {
                if (!it.isInt || it.asInt() < 1 || it.asInt() > 64) {
                    throw DslException(DslErrorKind.SCHEMA, "invalid max_depth")
                }
                it.asInt()
            } ?: DEFAULT_MAX_DEPTH
            return DslLimits(maxNodes, maxDepth)
        }

        private fun parseSignal(root: JsonNode, nodes: Map<String, JsonNode>, nodeTypes: Map<String, String>): DslSignal {
            val signal = root.get("signal")
            requireObject(signal, "signal")
            val nodeId = signal!!.get("node")?.asText()
            if (nodeId == null || nodeId !in nodes) {
                throw DslException(DslErrorKind.UNKNOWN_NODE, "signal node is not defined")
            }
            if (nodeTypes[nodeId] != "boolean") {
                throw DslException(DslErrorKind.TYPE, "signal node $nodeId must produce boolean")
            }
            val label = signal["label"]?.asText() ?: throw DslException(DslErrorKind.SCHEMA, "signal needs label")
            val reason = signal["reason"]?.asText() ?: throw DslException(DslErrorKind.SCHEMA, "signal needs reason")
            val riskTags = signal["risk_tags"]?.map { it.asText() } ?: emptyList()
            if (label.isEmpty() || reason.isEmpty()) throw DslException(DslErrorKind.SCHEMA, "signal label/reason cannot be empty")
            return DslSignal(nodeId, label, reason, riskTags)
        }

        private fun inferNodeTypes(
            nodes: Map<String, JsonNode>,
            parameters: Map<String, JsonNode>,
            inputs: Set<String>,
        ): Map<String, String> {
            val result = HashMap<String, String>()
            val visiting = HashSet<String>()
            fun infer(nodeId: String): String {
                result[nodeId]?.let { return it }
                if (!visiting.add(nodeId)) throw DslException(DslErrorKind.CYCLE, "node cycle detected through $nodeId")
                val node = nodes[nodeId] ?: throw DslException(DslErrorKind.UNKNOWN_NODE, "missing node $nodeId")
                val type = node["type"].asText()
                val inferred = when (type) {
                    "series" -> {
                        if (node["input"].asText() !in inputs) {
                            throw DslException(DslErrorKind.UNKNOWN_NODE, "node $nodeId uses undeclared input")
                        }
                        "number"
                    }
                    "value" -> if (node["value"].isBoolean) "boolean" else "number"
                    "parameter" -> {
                        val name = node["name"].asText()
                        if (name !in parameters) {
                            throw DslException(DslErrorKind.UNKNOWN_NODE, "node $nodeId references unknown parameter $name")
                        }
                        if (parameters.getValue(name)["type"].asText() == "boolean") "boolean" else "number"
                    }
                    "ifelse" -> {
                        val thenType = infer(node["then"].asText())
                        val elseType = infer(node["else"].asText())
                        if (thenType != elseType) {
                            throw DslException(DslErrorKind.TYPE, "ifelse node $nodeId mixes branch types")
                        }
                        thenType
                    }
                    in COMPARISON_TYPES,
                    in BOOLEAN_BINARY,
                    "not",
                    "crosses_above",
                    "crosses_below",
                    -> "boolean"
                    else -> "number"
                }
                visiting.remove(nodeId)
                result[nodeId] = inferred
                return inferred
            }
            for (nodeId in nodes.keys) infer(nodeId)
            return result
        }

        private fun validateDepth(
            nodeId: String,
            nodes: Map<String, JsonNode>,
            limits: DslLimits,
            memo: MutableMap<String, Int>,
        ): Int {
            memo[nodeId]?.let { return it }
            var depth = 1
            for (ref in refsOf(nodes.getValue(nodeId))) {
                val child = nodes[ref] ?: throw DslException(DslErrorKind.UNKNOWN_NODE, "missing node $ref")
                depth = maxOf(depth, 1 + validateDepth(ref, nodes, limits, memo))
            }
            if (depth > limits.maxDepth) {
                throw DslException(DslErrorKind.LIMIT, "node $nodeId depth $depth exceeds max_depth ${limits.maxDepth}")
            }
            memo[nodeId] = depth
            return depth
        }

        private fun validateOperandKinds(nodeId: String, node: JsonNode, nodeTypes: Map<String, String>) {
            val kind = node["type"].asText()
            val needsNumber =
                kind in NUMERIC_BINARY ||
                    kind in NUMERIC_UNARY ||
                    kind in COMPARISON_TYPES ||
                    kind in ROLLING_TYPES ||
                    kind == "lag" ||
                    kind == "crosses_above" ||
                    kind == "crosses_below"
            for (ref in refsOf(node)) {
                val refType = nodeTypes[ref] ?: throw DslException(DslErrorKind.UNKNOWN_NODE, "missing node $ref")
                if (needsNumber && refType != "number") {
                    throw DslException(DslErrorKind.TYPE, "node $nodeId requires numeric operand $ref")
                }
            }
            if (kind in BOOLEAN_BINARY) {
                for (ref in listOf(node["left"].asText(), node["right"].asText())) {
                    if (nodeTypes[ref] != "boolean") throw DslException(DslErrorKind.TYPE, "node $nodeId requires boolean operands")
                }
            }
            if (kind == "not" && nodeTypes[node["operand"].asText()] != "boolean") {
                throw DslException(DslErrorKind.TYPE, "not node $nodeId requires boolean operand")
            }
            if (kind == "ifelse" && nodeTypes[node["condition"].asText()] != "boolean") {
                throw DslException(DslErrorKind.TYPE, "ifelse node $nodeId requires boolean condition")
            }
        }

        private fun validateWindowRefs(
            nodeId: String,
            node: JsonNode,
            nodes: Map<String, JsonNode>,
            parameters: Map<String, JsonNode>,
        ) {
            if (node["type"].asText() !in ROLLING_TYPES || !node["window"].isTextual) return
            val windowRef = node["window"].asText()
            val target = nodes[windowRef] ?: throw DslException(DslErrorKind.UNKNOWN_NODE, "rolling node $nodeId window ref missing")
            if (target["type"].asText() != "parameter") {
                throw DslException(DslErrorKind.TYPE, "rolling node $nodeId window must be an integer parameter")
            }
            val name = target["name"].asText()
            if (parameters[name]?.get("type")?.asText() != "integer") {
                throw DslException(DslErrorKind.TYPE, "rolling node $nodeId window parameter $name must be integer")
            }
        }

        private fun refsOf(node: JsonNode): List<String> {
            val refs = mutableListOf<String>()
            for (key in NODE_REF_KEYS) {
                node.get(key)?.takeIf { it.isTextual }?.let { refs += it.asText() }
            }
            val window = node.get("window")
            if (window != null && window.isTextual) refs += window.asText()
            return refs
        }

        private fun parameterValue(type: String, value: JsonNode): Any = when (type) {
            "boolean" -> value.asBoolean()
            "integer" -> value.asInt()
            else -> value.asDouble()
        }

        private fun requireObject(node: JsonNode?, name: String) {
            if (node == null || !node.isObject) throw DslException(DslErrorKind.SCHEMA, "$name must be an object")
        }

        private fun text(root: JsonNode, field: String): String {
            val value = root.get(field)
            if (value == null || !value.isTextual || value.asText().isEmpty()) {
                throw DslException(DslErrorKind.SCHEMA, "missing $field")
            }
            return value.asText()
        }
    }
}
