package com.marketmonitor.app.market

import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.attribute.FileTime
import java.time.Instant
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class StoragePolicyTest {
    @Test
    fun cleanupDeletesOnlyColdPackagesAndSkipsActive() {
        val root = Files.createTempDirectory("mm-cold")
        try {
            val packages = root.resolve("packages")
            Files.createDirectories(packages)
            val old = packages.resolve("cold-1")
            val active = packages.resolve("active-1")
            val user = root.resolve("user.db")
            Files.createDirectories(old)
            Files.createDirectories(active)
            Files.write(old.resolve("bar.json"), ByteArray(100))
            Files.write(active.resolve("bar.json"), ByteArray(100))
            Files.write(user, ByteArray(50))
            Files.setLastModifiedTime(old, FileTime.from(Instant.parse("2026-01-01T00:00:00Z")))

            val decision = StoragePolicy.cleanup(root, activePackageIds = setOf("active-1"), availableBytes = 0, reserveBytes = 100)

            assertTrue(Files.exists(active))
            assertTrue(Files.exists(user))
            assertEquals(listOf("cold-1"), decision.deleted)
            assertEquals(100L, decision.freedBytes)
            assertTrue(decision.withinBudget)
        } finally {
            Files.walk(root).use { paths -> paths.sorted(Comparator.reverseOrder()).forEach { Files.deleteIfExists(it) } }
        }
    }

    @Test
    fun planKeepsActivePackageEvenUnderPressure() {
        val root = Files.createTempDirectory("mm-cold-plan")
        try {
            val packages = root.resolve("packages")
            Files.createDirectories(packages)
            val active = packages.resolve("active-1")
            Files.createDirectories(active)
            Files.write(active.resolve("bar.json"), ByteArray(1000))

            val decision = StoragePolicy.planCleanup(root, activePackageIds = setOf("active-1"), availableBytes = 0, reserveBytes = 5000)

            assertEquals(emptyList<String>(), decision.deleted)
            assertTrue(!decision.withinBudget)
        } finally {
            Files.walk(root).use { paths -> paths.sorted(Comparator.reverseOrder()).forEach { Files.deleteIfExists(it) } }
        }
    }
}
