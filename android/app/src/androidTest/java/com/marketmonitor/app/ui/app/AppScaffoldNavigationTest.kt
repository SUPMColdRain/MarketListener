package com.marketmonitor.app.ui.app

import androidx.compose.material3.Text
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import com.marketmonitor.app.ui.theme.MarketListenerTheme
import com.marketmonitor.app.ui.theme.ThemeMode
import org.junit.Rule
import org.junit.Test

/** Instrumented Compose test: every first-level destination is reachable. */
class AppScaffoldNavigationTest {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun allFiveSectionsAreReachableFromBottomNavigation() {
        composeRule.setContent {
            MarketListenerTheme(ThemeMode.DARK) {
                var section by remember { mutableStateOf(AppSection.MARKET) }
                AppScaffold(
                    section = section,
                    onSectionChange = { section = it },
                    onOpenSettings = {},
                ) {
                    Text("screen:${section.name}")
                }
            }
        }

        AppSection.entries.forEach { section ->
            composeRule.onNodeWithContentDescription(section.label, useUnmergedTree = true).performClick()
            composeRule.onNodeWithText("screen:${section.name}").assertIsDisplayed()
        }
    }
}
