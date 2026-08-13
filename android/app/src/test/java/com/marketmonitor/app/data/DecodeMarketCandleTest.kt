package com.marketmonitor.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class DecodeMarketCandleTest {
    @Test
    fun decodeMarketCandlePreservesOffsetTimestamps() {
        val json =
            """
            {
              "bar_open_time": "2026-08-03T09:30:00+08:00",
              "bar_close_time": "2026-08-03T10:00:00+08:00",
              "open": 100.0,
              "high": 102.0,
              "low": 99.0,
              "close": 101.0,
              "source": {"provider": "test"},
              "quality_status": "PASS"
            }
            """.trimIndent()

        val candle = decodeMarketCandle(json)

        assertNotNull(candle)
        assertEquals(101.0, candle!!.close, 0.0)
        assertEquals("test", candle.source)
        assertEquals("PASS", candle.qualityStatus)
    }

    @Test
    fun decodeMarketCandleRejectsNaiveTimestamps() {
        val json =
            """
            {
              "bar_open_time": "2026-08-03T01:30:00",
              "bar_close_time": "2026-08-03T02:00:00",
              "open": 100.0,
              "high": 102.0,
              "low": 99.0,
              "close": 101.0,
              "source": {"provider": "test"},
              "quality_status": "PASS"
            }
            """.trimIndent()

        assertNull(decodeMarketCandle(json))
    }
}
