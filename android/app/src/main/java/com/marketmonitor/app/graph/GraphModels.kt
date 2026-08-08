package com.marketmonitor.app.graph

import org.json.JSONArray
import org.json.JSONObject

/** Immutable value types for one offline industry-graph snapshot. */
data class GraphLocation(
    val page: Int? = null,
    val cell: String? = null,
    val dom: String? = null,
    val line: Int? = null,
    val offset: Int? = null,
) {
    fun summary(): String = when {
        dom != null -> "DOM：$dom"
        cell != null -> "单元格：$cell"
        page != null && line != null -> "第 $page 页 第 $line 行"
        line != null -> "第 $line 行"
        else -> "未知定位"
    }

    companion object {
        fun parse(raw: JSONObject): GraphLocation = GraphLocation(
            page = raw.optIntOrNull("page"),
            cell = raw.optStringOrNull("cell"),
            dom = raw.optStringOrNull("dom"),
            line = raw.optIntOrNull("line"),
            offset = raw.optIntOrNull("offset"),
        )
    }
}

data class GraphEvidence(
    val evidenceId: String,
    val sourceId: String,
    val sourceType: String,
    val location: GraphLocation,
    val parsedVersion: String,
    val extractedAt: String,
    val sha256: String,
) {
    companion object {
        fun parse(raw: JSONObject): GraphEvidence = GraphEvidence(
            evidenceId = raw.getString("evidence_id"),
            sourceId = raw.getString("source_id"),
            sourceType = raw.getString("source_type"),
            location = GraphLocation.parse(raw.getJSONObject("location")),
            parsedVersion = raw.getString("parsed_version"),
            extractedAt = raw.getString("extracted_at"),
            sha256 = raw.optString("sha256"),
        )
    }
}

data class GraphEntity(
    val entityId: String,
    val entityType: String,
    val name: String,
    val normalizedName: String,
    val aliases: List<String>,
) {
    val displayName: String get() = name

    companion object {
        fun parse(raw: JSONObject): GraphEntity = GraphEntity(
            entityId = raw.getString("entity_id"),
            entityType = raw.getString("entity_type"),
            name = raw.getString("name"),
            normalizedName = raw.getString("normalized_name"),
            aliases = raw.optJSONArray("aliases")?.toStringList().orEmpty(),
        )
    }
}

data class GraphRelationship(
    val relationshipId: String,
    val relationshipType: String,
    val sourceEntityId: String,
    val targetEntityId: String,
    val direction: String,
    val confidence: Double,
    val confirmationStatus: String,
    val evidenceIds: List<String>,
    val version: Int,
) {
    companion object {
        fun parse(raw: JSONObject): GraphRelationship = GraphRelationship(
            relationshipId = raw.getString("relationship_id"),
            relationshipType = raw.getString("relationship_type"),
            sourceEntityId = raw.getString("source_entity_id"),
            targetEntityId = raw.getString("target_entity_id"),
            direction = raw.getString("direction"),
            confidence = raw.getDouble("confidence"),
            confirmationStatus = raw.getString("confirmation_status"),
            evidenceIds = raw.optJSONArray("evidence_ids")?.toStringList().orEmpty(),
            version = raw.optInt("version", 1),
        )
    }
}

data class GraphSnapshot(
    val entities: List<GraphEntity>,
    val evidence: List<GraphEvidence>,
    val relationships: List<GraphRelationship>,
) {
    companion object {
        fun parse(text: String): GraphSnapshot = parse(JSONObject(text))

        fun parse(raw: JSONObject): GraphSnapshot {
            val entities = raw.getJSONArray("entities").toList().map(GraphEntity::parse)
            val evidence = raw.optJSONArray("evidence")?.toList().orEmpty().map(GraphEvidence::parse)
            val relationships = raw.optJSONArray("relationships")?.toList().orEmpty().map(GraphRelationship::parse)
            return GraphSnapshot(entities, evidence, relationships)
        }
    }
}

private fun JSONObject.optIntOrNull(name: String): Int? =
    if (has(name) && !isNull(name)) getInt(name) else null

private fun JSONObject.optStringOrNull(name: String): String? =
    if (has(name) && !isNull(name)) getString(name) else null

private fun JSONArray.toList(): List<JSONObject> = buildList {
    for (index in 0 until length()) add(getJSONObject(index))
}

private fun JSONArray.toStringList(): List<String> = buildList {
    for (index in 0 until length()) add(getString(index))
}
