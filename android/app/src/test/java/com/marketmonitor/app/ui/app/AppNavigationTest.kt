package com.marketmonitor.app.ui.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AppNavigationTest {

    @Test
    fun fiveFirstLevelSectionsExistInOrder() {
        assertEquals(5, AppSection.entries.size)
        assertEquals(
            listOf("行情", "数据", "策略", "统计", "产业链"),
            AppSection.entries.map { it.label },
        )
    }

    @Test
    fun everySectionHasAnIcon() {
        AppSection.entries.forEach { section ->
            assertTrue("${section.label} must have a real vector icon", section.icon.name.isNotEmpty())
        }
    }
}
