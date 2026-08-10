package com.marketmonitor.app

import android.content.Context
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.marketmonitor.app.graph.GraphSearchState
import com.marketmonitor.app.ui.app.MarketListenerApp
import com.marketmonitor.app.ui.market.MarketImportUiState
import com.marketmonitor.app.ui.theme.ThemeMode
import com.marketmonitor.app.ui.theme.ThemeRepository
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** End-to-end app shell smoke test on device/emulator. */
@RunWith(AndroidJUnit4::class)
class MarketListenerAppSmokeTest {

    @get:Rule
    val composeRule = createComposeRule()

    private val context: Context = ApplicationProvider.getApplicationContext()

    @Test
    fun appShellOpensSettingsAndPersistsDarkChoice() {
        val themeRepository = ThemeRepository(context)
        composeRule.setContent {
            MarketListenerApp(
                themeRepository = themeRepository,
                importState = MarketImportUiState(),
                marketData = null,
                onImport = {},
                onSyncFromServer = {},
                activePackageId = null,
                onCleanColdData = { 0L },
                graphRepository = null,
                graphState = GraphSearchState(),
                onGraphQueryChange = {},
                onGraphSelectEntity = {},
                onGraphSelectRelationship = {},
                onGraphImport = {},
                industryAtlasFile = null,
            )
        }

        listOf("行情", "数据", "策略", "统计", "产业链").forEach { label ->
            composeRule.onNodeWithContentDescription(label, useUnmergedTree = true).assertExists()
        }

        composeRule.onNodeWithContentDescription("数据", useUnmergedTree = true).performClick()
        composeRule.onNodeWithText("搜索指标（名称/代码）", useUnmergedTree = true).assertIsDisplayed()

        composeRule.onNodeWithContentDescription("设置", useUnmergedTree = true).performClick()
        composeRule.onNodeWithText("外观", useUnmergedTree = true).assertIsDisplayed()
        composeRule.onNodeWithText("深色", useUnmergedTree = true).performClick()
        composeRule.waitUntil(timeoutMillis = 5_000) {
            runBlocking { themeRepository.themeMode.first() } == ThemeMode.DARK
        }
        composeRule.onNodeWithText("完成", useUnmergedTree = true).performClick()

        val persisted = runBlocking { themeRepository.themeMode.first() }
        assertEquals(ThemeMode.DARK, persisted)

        runBlocking { themeRepository.setThemeMode(ThemeMode.SYSTEM) }
    }
}
