package com.marketmonitor.app.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import com.marketmonitor.app.ui.theme.MarketListenerTheme
import com.marketmonitor.app.ui.theme.ThemeMode
import org.junit.Rule
import org.junit.Test

/** Instrumented Compose test: missing data renders guidance, never zero. */
class DataScreenEmptyStateTest {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun missingMarketDataShowsGuidanceInsteadOfZero() {
        composeRule.setContent {
            MarketListenerTheme(ThemeMode.DARK) {
                DataScreen(marketData = null)
            }
        }

        composeRule.onNodeWithText("无已导入行情包").assertIsDisplayed()
        composeRule.onNodeWithText(
            "尚未同步指标数据。请先在“行情”页从电脑同步行情包，或导入包含 gold_metrics 的行情包。",
        ).assertIsDisplayed()
    }
}
