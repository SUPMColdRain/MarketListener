package com.marketmonitor.app.ui.chart

import androidx.compose.ui.graphics.Color
import com.marketmonitor.app.data.MarketCandle
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class KlineChartHtmlTest {

    private val candle = MarketCandle(
        openTimeSeconds = 1_785_720_600L,
        open = 10.0,
        high = 11.0,
        low = 9.5,
        close = 10.5,
        source = "fixture",
        qualityStatus = "PASS",
    )

    private fun theme(
        background: Color = Color(0xFF0B0E14),
        text: Color = Color(0xFFE8EDF5),
        grid: Color = Color(0xFF232D3D),
        axis: Color = Color(0xFF929EAF),
        up: Color = Color(0xFFFF5A5F),
        down: Color = Color(0xFF2BBF8C),
        accent: Color = Color(0xFF2962FF),
    ) = ChartTheme(
        background = background,
        textPrimary = text,
        textSecondary = Color(0xFF929EAF),
        grid = grid,
        axis = axis,
        accent = accent,
        priceUp = up,
        priceDown = down,
        flat = Color(0xFF929EAF),
        warning = Color(0xFFF5A623),
        error = Color(0xFFFF6B6B),
        info = Color(0xFF4DA3FF),
        highlight = Color(0xFFFFD166),
    )

    @Test
    fun darkThemeColorsAreInjectedIntoHtml() {
        val html = buildKlineHtml(listOf(candle), theme(), "暂无数据", 320)

        assertTrue(html.contains("#0b0e14"))
        assertTrue(html.contains("#e8edf5"))
        assertTrue(html.contains("#232d3d"))
        assertTrue(html.contains("#929eaf"))
        assertTrue(html.contains("#ff5a5f"))
        assertTrue(html.contains("#2bbf8c"))
        assertTrue(html.contains("#2962ff"))
        assertTrue(html.contains("lightweight-charts.standalone.production.js"))
    }

    @Test
    fun lightThemeColorsAreInjectedIntoHtml() {
        val html = buildKlineHtml(
            listOf(candle),
            theme(
                background = Color(0xFFF5F7FA),
                text = Color(0xFF11151C),
                grid = Color(0xFFE1E6EE),
                axis = Color(0xFF687386),
                up = Color(0xFFD9383F),
                down = Color(0xFF0E9F6E),
                accent = Color(0xFF2962FF),
            ),
            "暂无数据",
            320,
        )

        assertTrue(html.contains("#f5f7fa"))
        assertTrue(html.contains("#11151c"))
        assertTrue(html.contains("#e1e6ee"))
        assertTrue(html.contains("#687386"))
        assertTrue(html.contains("#d9383f"))
        assertTrue(html.contains("#0e9f6e"))
    }

    @Test
    fun emptyStateEscapesHtmlAndNeverLeaksUndefined() {
        val html = buildKlineHtml(emptyList(), theme(), "<b>暂无数据</b>", 320)

        assertTrue(html.contains("&lt;b&gt;暂无数据&lt;/b&gt;"))
        assertFalse(html.contains("<b>暂无数据</b>"))
        assertFalse(html.contains("undefined"))
        assertTrue(html.contains("id='empty'"))
    }

    @Test
    fun candleDataUsesRealOpenHighLowClose() {
        val html = buildKlineHtml(listOf(candle), theme(), "暂无数据", 320)

        assertTrue(Regex("\"open\":10(?=[,}])").containsMatchIn(html))
        assertTrue(Regex("\"high\":11(?=[,}])").containsMatchIn(html))
        assertTrue(html.contains("\"low\":9.5"))
        assertTrue(html.contains("\"close\":10.5"))
        assertFalse(html.contains("undefined"))
        assertEquals(1, Regex("time\":1785720600").findAll(html).count())
    }
}
