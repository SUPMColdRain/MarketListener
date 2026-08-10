package com.marketmonitor.app.ui.chart

import androidx.compose.ui.graphics.Color
import com.marketmonitor.app.ui.data.UiHeatmapCell
import com.marketmonitor.app.ui.data.UiMetricPanel
import com.marketmonitor.app.ui.data.UiMetricPoint
import com.marketmonitor.app.ui.data.UiMetricSeries
import com.marketmonitor.app.ui.data.UiPanelKind
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class EChartsOptionBuilderTest {

    private val theme = ChartTheme(
        background = Color(0xFF0B0E14),
        textPrimary = Color(0xFFE8EDF5),
        textSecondary = Color(0xFF929EAF),
        grid = Color(0xFF232D3D),
        axis = Color(0xFF929EAF),
        accent = Color(0xFF2962FF),
        priceUp = Color(0xFFFF5A5F),
        priceDown = Color(0xFF2BBF8C),
        flat = Color(0xFF929EAF),
        warning = Color(0xFFF5A623),
        error = Color(0xFFFF6B6B),
        info = Color(0xFF4DA3FF),
        highlight = Color(0xFFFFD166),
    )

    @Test
    fun lineOptionIsStructuredJsonWithSeriesAndThemeColors() {
        val series = listOf(
            UiMetricSeries(
                seriesId = "breadth:advances",
                name = "上涨家数",
                points = listOf(
                    UiMetricPoint(1_700_000_000_000L, 2800.0, "2026-08-01"),
                    UiMetricPoint(1_700_086_400_000L, 3100.0, "2026-08-02"),
                ),
                latestValue = 3100.0,
                latestLabel = "2026-08-02",
            ),
        )

        val option = JSONObject(EChartsOptionBuilder.buildLineOption(series, theme, area = true))

        assertEquals("transparent", option.getString("backgroundColor"))
        assertEquals("line", option.getJSONArray("series").getJSONObject(0).getString("type"))
        assertTrue(option.getJSONArray("series").getJSONObject(0).has("areaStyle"))
        assertEquals(2, option.getJSONObject("xAxis").getJSONArray("data").length())
        assertTrue(option.toString().contains("#2962ff"))
    }

    @Test
    fun emptyLineOptionReturnsEmptyJsonObject() {
        assertEquals("{}", EChartsOptionBuilder.buildLineOption(emptyList(), theme, area = false))
    }

    @Test
    fun heatmapOptionUsesRealMinMaxAndNormalizedCells() {
        val panel = UiMetricPanel(
            panelId = "heat",
            title = "期货持仓热力图",
            kind = UiPanelKind.HEATMAP,
            heatmap = listOf(
                UiHeatmapCell("AU", "2026-08-01", 100.0, 0.0),
                UiHeatmapCell("AG", "2026-08-01", 300.0, 1.0),
            ),
        )

        val option = JSONObject(EChartsOptionBuilder.buildHeatmapOption(panel, theme))
        val visualMap = option.getJSONObject("visualMap")

        assertEquals(100.0, visualMap.getDouble("min"), 0.0)
        assertEquals(300.0, visualMap.getDouble("max"), 0.0)
        assertEquals("heatmap", option.getJSONArray("series").getJSONObject(0).getString("type"))
        assertEquals(2, option.getJSONArray("series").getJSONObject(0).getJSONArray("data").length())
        assertTrue(option.toString().contains("#0b0e14"))
    }

    @Test
    fun emptyHeatmapReturnsEmptyJsonObject() {
        val panel = UiMetricPanel(
            panelId = "heat",
            title = "空",
            kind = UiPanelKind.HEATMAP,
        )
        assertEquals("{}", EChartsOptionBuilder.buildHeatmapOption(panel, theme))
    }
}
