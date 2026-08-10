package com.marketmonitor.app.ui.settings

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import com.marketmonitor.app.ui.theme.MarketListenerTheme
import com.marketmonitor.app.ui.theme.ThemeMode
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test

/** Instrumented Compose test: all three theme choices are selectable. */
class SettingsDialogTest {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun systemLightDarkOptionsAreSelectable() {
        var selected = ThemeMode.SYSTEM
        composeRule.setContent {
            MarketListenerTheme(ThemeMode.SYSTEM) {
                SettingsDialog(
                    current = selected,
                    onSelect = { selected = it },
                    onDismiss = {},
                )
            }
        }

        composeRule.onNodeWithText("外观").assertIsDisplayed()
        composeRule.onNodeWithText("跟随系统").assertIsDisplayed()
        composeRule.onNodeWithText("浅色").performClick()
        assertEquals(ThemeMode.LIGHT, selected)
        composeRule.onNodeWithText("深色").performClick()
        assertEquals(ThemeMode.DARK, selected)
        composeRule.onNodeWithText("跟随系统").performClick()
        assertEquals(ThemeMode.SYSTEM, selected)
    }
}
