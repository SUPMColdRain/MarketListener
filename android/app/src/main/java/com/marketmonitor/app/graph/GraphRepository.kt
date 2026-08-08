package com.marketmonitor.app.graph

/** Offline query layer for one graph snapshot. */
class GraphRepository private constructor(
    private val snapshot: GraphSnapshot,
) {
    private val entitiesById: Map<String, GraphEntity> = snapshot.entities.associateBy(GraphEntity::entityId)
    private val evidenceById: Map<String, GraphEvidence> = snapshot.evidence.associateBy(GraphEvidence::evidenceId)

    fun search(query: String): List<GraphEntity> {
        val keyword = query.trim()
        if (keyword.isEmpty()) return emptyList()
        return snapshot.entities
            .filter { entity ->
                val fields = listOf(entity.name, entity.normalizedName) + entity.aliases
                fields.any { it.contains(keyword, ignoreCase = true) }
            }
            .sortedWith(compareBy<GraphEntity> { it.entityType }.thenBy { it.normalizedName })
    }

    fun entityFor(entityId: String): GraphEntity? = entitiesById[entityId]

    fun relationshipsFor(entityId: String): List<GraphRelationship> =
        snapshot.relationships
            .filter { it.sourceEntityId == entityId || it.targetEntityId == entityId }
            .sortedWith(
                compareBy<GraphRelationship> { it.confirmationStatus }
                    .thenByDescending(GraphRelationship::confidence)
                    .thenBy(GraphRelationship::relationshipId),
            )

    fun evidenceFor(evidenceId: String): GraphEvidence? = evidenceById[evidenceId]

    fun relationshipDetail(relationshipId: String): GraphRelationshipDetail? {
        val relationship = snapshot.relationships.firstOrNull { it.relationshipId == relationshipId } ?: return null
        val source = entitiesById[relationship.sourceEntityId] ?: return null
        val target = entitiesById[relationship.targetEntityId] ?: return null
        val evidence = relationship.evidenceIds.mapNotNull(evidenceById::get)
        return GraphRelationshipDetail(
            relationship = relationship,
            source = source,
            target = target,
            evidence = evidence,
        )
    }

    fun allEntities(): List<GraphEntity> = snapshot.entities

    companion object {
        fun fromJson(text: String): GraphRepository = GraphRepository(GraphSnapshot.parse(text))
    }
}

data class GraphRelationshipDetail(
    val relationship: GraphRelationship,
    val source: GraphEntity,
    val target: GraphEntity,
    val evidence: List<GraphEvidence>,
)
