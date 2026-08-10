package com.marketmonitor.app.ui.chart

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import com.marketmonitor.app.ui.theme.MarketListenerTheme
import com.marketmonitor.app.ui.theme.ThemeMode
import org.junit.Rule
import org.junit.Test

/** Instrumented Compose test: both chart surfaces compose a WebView. */
class ChartSurfaceRenderTest {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun tradingChartWebViewIsComposed() {
        composeRule.setContent {
            MarketListenerTheme(ThemeMode.DARK) {
                TradingChartView(
                    candles = emptyList(),
                    emptyMessage = "尚未导入行情数据",
                )
            }
        }

        composeRule.onNodeWithTag("trading-chart").assertExists()
    }

    @Test
    fun echartsWebViewIsComposed() {
        composeRule.setContent {
            MarketListenerTheme(ThemeMode.LIGHT) {
                EChartsView(optionJson = "{}")
            }
        }

        composeRule.onNodeWithTag("echarts-chart").assertExists()
    }
}
