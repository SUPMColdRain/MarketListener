package com.marketmonitor.app.ui.theme

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith

/** Instrumented test: the theme choice survives repository recreation. */
@RunWith(AndroidJUnit4::class)
class ThemeRepositoryInstrumentedTest {

    private val context: Context = ApplicationProvider.getApplicationContext()

    @Test
    fun themeChoicePersistsAcrossRepositoryInstances() = runBlocking {
        val repository = ThemeRepository(context)
        try {
            repository.setThemeMode(ThemeMode.LIGHT)
            val reloaded = ThemeRepository(context)
            assertEquals(ThemeMode.LIGHT, reloaded.themeMode.first())

            repository.setThemeMode(ThemeMode.DARK)
            val reloadedAgain = ThemeRepository(context)
            assertEquals(ThemeMode.DARK, reloadedAgain.themeMode.first())
        } finally {
            repository.setThemeMode(ThemeMode.SYSTEM)
        }
    }
}
