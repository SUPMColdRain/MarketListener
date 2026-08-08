package com.marketmonitor.app.market

import java.io.IOException
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.attribute.FileTime
import java.time.Instant
import java.util.stream.Collectors

/**
 * Cold-shard cleanup policy.
 *
 * Only directories directly under ``coldRoot/packages`` are ever considered
 * for deletion; the active package and the personal user database are outside
 * this policy's scope by construction.
 */
data class StorageDecision(
    val deleted: List<String>,
    val freedBytes: Long,
    val withinBudget: Boolean,
)

object StoragePolicy {
    fun planCleanup(
        coldRoot: Path,
        activePackageIds: Set<String>,
        availableBytes: Long,
        reserveBytes: Long,
        now: Instant = Instant.now(),
    ): StorageDecision {
        val packages = coldRoot.resolve("packages")
        if (!Files.isDirectory(packages)) {
            return StorageDecision(emptyList(), 0L, availableBytes >= reserveBytes)
        }
        val candidates = Files.list(packages).use { stream ->
            stream
                .filter { Files.isDirectory(it) }
                .filter { it.fileName.toString() !in activePackageIds }
                .collect(Collectors.toList())
        }
        val byAge = candidates.sortedBy { lastModifiedMillis(it, now) }
        val toDelete = mutableListOf<String>()
        var freed = 0L
        var currentAvailable = availableBytes
        for (directory in byAge) {
            if (currentAvailable >= reserveBytes) break
            val size = directorySize(directory)
            toDelete += directory.fileName.toString()
            freed += size
            currentAvailable += size
        }
        return StorageDecision(toDelete, freed, currentAvailable >= reserveBytes)
    }

    fun cleanup(
        coldRoot: Path,
        activePackageIds: Set<String>,
        availableBytes: Long,
        reserveBytes: Long,
        now: Instant = Instant.now(),
    ): StorageDecision {
        val plan = planCleanup(coldRoot, activePackageIds, availableBytes, reserveBytes, now)
        val packages = coldRoot.resolve("packages")
        plan.deleted.forEach { name ->
            val target = packages.resolve(name).normalize()
            if (!target.startsWith(packages.normalize())) {
                throw IOException("refusing to delete outside package root: $target")
            }
            Files.walk(target).use { paths ->
                paths.sorted(Comparator.reverseOrder()).forEach { Files.deleteIfExists(it) }
            }
        }
        return plan
    }

    private fun lastModifiedMillis(directory: Path, now: Instant): Long = try {
        val attribute = Files.getLastModifiedTime(directory)
        if (attribute.toMillis() <= 0) now.toEpochMilli() else attribute.toMillis()
    } catch (_: Exception) {
        now.toEpochMilli()
    }

    private fun directorySize(directory: Path): Long = try {
        Files.walk(directory).use { paths ->
            paths.filter { Files.isRegularFile(it) }.mapToLong { path ->
                try {
                    Files.size(path)
                } catch (_: Exception) {
                    0L
                }
            }.sum()
        }
    } catch (_: Exception) {
        0L
    }
}
