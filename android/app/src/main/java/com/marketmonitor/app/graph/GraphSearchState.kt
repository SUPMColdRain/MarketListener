package com.marketmonitor.app.graph

/** Pure UI state for the industry-graph tab. */
data class GraphSearchState(
    val query: String = "",
    val results: List<GraphEntity> = emptyList(),
    val selectedEntityId: String? = null,
    val selectedRelationshipId: String? = null,
    val error: String? = null,
    val snapshotLoaded: Boolean = false,
)

fun GraphSearchState.applyQuery(repository: GraphRepository?, keyword: String): GraphSearchState {
    if (repository == null) {
        return copy(query = keyword, results = emptyList(), error = "尚未导入图谱数据")
    }
    return copy(
        query = keyword,
        results = repository.search(keyword),
        selectedEntityId = null,
        selectedRelationshipId = null,
        error = null,
        snapshotLoaded = true,
    )
}

fun GraphSearchState.selectEntity(repository: GraphRepository?, entityId: String): GraphSearchState {
    if (repository == null || repository.entityFor(entityId) == null) {
        return copy(error = "找不到所选实体")
    }
    return copy(selectedEntityId = entityId, selectedRelationshipId = null, error = null)
}

fun GraphSearchState.selectRelationship(repository: GraphRepository?, relationshipId: String): GraphSearchState {
    if (repository == null || repository.relationshipDetail(relationshipId) == null) {
        return copy(error = "找不到所选关系")
    }
    return copy(selectedRelationshipId = relationshipId, error = null)
}

fun GraphSearchState.loaded(repository: GraphRepository?): GraphSearchState =
    if (repository == null) {
        copy(snapshotLoaded = false, error = "尚未导入图谱数据")
    } else {
        copy(snapshotLoaded = true, error = null)
    }
