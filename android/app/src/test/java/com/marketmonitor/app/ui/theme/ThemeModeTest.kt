package com.marketmonitor.app.ui.theme

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ThemeModeTest {

    @Test
    fun systemFollowsDeviceNightMode() {
        assertTrue(resolveIsDark(ThemeMode.SYSTEM, systemInDark = true))
        assertFalse(resolveIsDark(ThemeMode.SYSTEM, systemInDark = false))
    }

    @Test
    fun lightAlwaysUsesLightScheme() {
        assertFalse(resolveIsDark(ThemeMode.LIGHT, systemInDark = true))
        assertFalse(resolveIsDark(ThemeMode.LIGHT, systemInDark = false))
    }

    @Test
    fun darkAlwaysUsesDarkScheme() {
        assertTrue(resolveIsDark(ThemeMode.DARK, systemInDark = true))
        assertTrue(resolveIsDark(ThemeMode.DARK, systemInDark = false))
    }

    @Test
    fun storageValuesRoundTrip() {
        ThemeMode.entries.forEach { mode ->
            assertEquals(mode, ThemeMode.fromStorage(mode.storageValue))
        }
        assertEquals(ThemeMode.SYSTEM, ThemeMode.fromStorage("system"))
        assertEquals(ThemeMode.LIGHT, ThemeMode.fromStorage("light"))
        assertEquals(ThemeMode.DARK, ThemeMode.fromStorage("dark"))
    }

    @Test
    fun unknownStorageValueFallsBackToSystem() {
        assertEquals(ThemeMode.SYSTEM, ThemeMode.fromStorage(null))
        assertEquals(ThemeMode.SYSTEM, ThemeMode.fromStorage("neon"))
    }
}
