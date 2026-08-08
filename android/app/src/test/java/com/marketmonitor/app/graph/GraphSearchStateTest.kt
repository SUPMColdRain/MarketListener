package com.marketmonitor.app.graph

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class GraphSearchStateTest {
    private val repository = GraphRepository.fromJson(resource("graph/snapshot.json"))

    @Test
    fun loadWithoutSnapshotShowsEmptyState() {
        val state = GraphSearchState().loaded(null)
        assertTrue(!state.snapshotLoaded)
        assertEquals("尚未导入图谱数据", state.error)
    }

    @Test
    fun queryTransitionsUpdateResultsAndSelection() {
        val afterQuery = GraphSearchState().applyQuery(repository, "茅台")
        assertEquals(2, afterQuery.results.size)
        assertTrue(afterQuery.snapshotLoaded)
        assertNull(afterQuery.error)

        val afterSelect = afterQuery.selectEntity(repository, "company.600519")
        assertEquals("company.600519", afterSelect.selectedEntityId)
        assertNull(afterSelect.error)

        val afterRelationship = afterSelect.selectRelationship(repository, "rel.supplies.0001")
        assertEquals("rel.supplies.0001", afterRelationship.selectedRelationshipId)
        assertNull(afterRelationship.error)
    }

    @Test
    fun queryWithoutRepositoryReportsError() {
        val state = GraphSearchState().applyQuery(null, "茅台")
        assertTrue(state.results.isEmpty())
        assertEquals("尚未导入图谱数据", state.error)
    }

    @Test
    fun unknownSelectionReportsErrorWithoutChangingSelection() {
        val state = GraphSearchState().applyQuery(repository, "茅台")
        val broken = state.selectEntity(repository, "missing")
        assertEquals("找不到所选实体", broken.error)
        assertNull(broken.selectedEntityId)

        val brokenRelationship = state.selectRelationship(repository, "missing")
        assertEquals("找不到所选关系", brokenRelationship.error)
    }

    private fun resource(name: String): String = javaClass.classLoader
        ?.getResourceAsStream(name)
        ?.bufferedReader()
        ?.use { it.readText() }
        ?: error("Missing test resource: $name")
}
