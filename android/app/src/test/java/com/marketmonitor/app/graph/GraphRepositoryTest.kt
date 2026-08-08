package com.marketmonitor.app.graph

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class GraphRepositoryTest {
    private val repository = GraphRepository.fromJson(resource("graph/snapshot.json"))

    @Test
    fun searchMatchesNameAliasAndNormalizedName() {
        val byAlias = repository.search("茅台")
        assertEquals(2, byAlias.size)
        assertTrue(byAlias.any { it.entityId == "company.600519" })
        assertTrue(byAlias.any { it.entityId == "product.maotai" })

        val byNormalized = repository.search("华致酒行")
        assertEquals(1, byNormalized.size)
        assertEquals("company.huazhi", byNormalized.single().entityId)

        assertTrue(repository.search("").isEmpty())
        assertTrue(repository.search("不存在的公司").isEmpty())
    }

    @Test
    fun relationshipsForEntityAreReturnedWithBothDirections() {
        val relationships = repository.relationshipsFor("company.600519")
        assertEquals(2, relationships.size)
        assertTrue(relationships.any { it.relationshipId == "rel.supplies.0001" })
        assertTrue(relationships.any { it.relationshipId == "rel.produces.0001" })
    }

    @Test
    fun relationshipDetailTracesBackToSourceEvidenceAndConfirmationStatus() {
        val detail = repository.relationshipDetail("rel.supplies.0001")
        requireNotNull(detail)
        assertEquals("company.600519", detail.source.entityId)
        assertEquals("company.huazhi", detail.target.entityId)
        assertEquals("AUTO_ACCEPTED", detail.relationship.confirmationStatus)
        assertEquals(1, detail.evidence.size)
        assertTrue(detail.evidence.single().location.summary().contains("DOM"))

        val confirmed = repository.relationshipDetail("rel.produces.0001")
        requireNotNull(confirmed)
        assertEquals("HUMAN_CONFIRMED", confirmed.relationship.confirmationStatus)
        assertEquals("第 2 行", confirmed.evidence.single().location.summary())
    }

    @Test
    fun unknownIdsReturnNull() {
        assertNull(repository.entityFor("missing"))
        assertNull(repository.evidenceFor("missing"))
        assertNull(repository.relationshipDetail("missing"))
    }

    private fun resource(name: String): String = javaClass.classLoader
        ?.getResourceAsStream(name)
        ?.bufferedReader()
        ?.use { it.readText() }
        ?: error("Missing test resource: $name")
}
