package com.marketmonitor.app

import com.marketmonitor.app.data.DatabaseBoundary
import org.junit.Assert.assertEquals
import org.junit.Test

class DatabaseBoundaryTest {
    @Test
    fun personalAndMarketStorageNamesRemainSeparate() {
        assertEquals("user.db", DatabaseBoundary.userDatabaseName)
        assertEquals("market_hot.db", DatabaseBoundary.marketDatabaseName)
        assertEquals("market-cold", DatabaseBoundary.marketColdDirectory)
    }
}
