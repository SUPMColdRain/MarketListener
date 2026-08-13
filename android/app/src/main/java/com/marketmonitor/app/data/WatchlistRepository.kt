package com.marketmonitor.app.data

import java.time.Instant

class WatchlistRepository(private val database: UserDatabase) {
    suspend fun add(instrumentId: String) {
        database.watchlistDao().add(WatchlistEntity(instrumentId, Instant.now().toString()))
    }

    suspend fun remove(instrumentId: String) {
        database.watchlistDao().remove(instrumentId)
    }

    suspend fun all(): List<String> = database.watchlistDao().all().map { it.instrumentId }
}
