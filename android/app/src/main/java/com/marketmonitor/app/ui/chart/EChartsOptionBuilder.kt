package com.marketmonitor.app.ui.chart

import com.marketmonitor.app.ui.data.UiMetricPanel
import com.marketmonitor.app.ui.data.UiMetricSeries
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import org.json.JSONArray
import org.json.JSONObject

/**
 * Builds ECharts options as structured JSON from viewer-only UI models.
 * UI screens never assemble raw JS option strings themselves.
 */
object EChartsOptionBuilder {

    fun buildLineOption(
        series: List<UiMetricSeries>,
        theme: ChartTheme,
        area: Boolean,
    ): String {
        val epochs = series
            .flatMap { it.points.map { point -> point.epochMillis } }
            .distinct()
            .sorted()
        if (epochs.isEmpty()) return "{}"

        val spanDays = (epochs.last() - epochs.first()) / 86_400_000L
        val formatter = if (spanDays > 300) YEAR_FORMAT else MONTH_DAY_FORMAT
        val labels = JSONArray().apply { epochs.forEach { put(formatter.format(Instant.ofEpochMilli(it).atZone(ZoneId.of("UTC")))) } }
        val palette = palette(theme)

        val seriesArray = JSONArray()
        series.forEachIndexed { index, uiSeries ->
            val valuesByEpoch = uiSeries.points.associate { it.epochMillis to it.value }
            val data = JSONArray().apply {
                epochs.forEach { epoch ->
                    val value = valuesByEpoch[epoch]
                    put(if (value == null) JSONObject.NULL else value)
                }
            }
            val color = palette[index % palette.size]
            val item = JSONObject()
                .put("name", uiSeries.name)
                .put("type", "line")
                .put("data", data)
                .put("showSymbol", false)
                .put("connectNulls", false)
                .put("smooth", false)
                .put("lineStyle", JSONObject().put("width", 1.5f).put("color", color))
                .put("itemStyle", JSONObject().put("color", color))
            if (area) {
                item.put("areaStyle", JSONObject().put("opacity", 0.12f).put("color", color))
            }
            seriesArray.put(item)
        }

        return JSONObject()
            .put("backgroundColor", "transparent")
            .put("animation", false)
            .put(
                "textStyle",
                JSONObject().put("color", theme.textPrimary.toHex()),
            )
            .put(
                "tooltip",
                JSONObject()
                    .put("trigger", "axis")
                    .put(
                        "textStyle",
                        JSONObject().put("color", theme.textPrimary.toHex()).put("fontSize", 11),
                    )
                    .put("backgroundColor", theme.background.toHex())
                    .put("borderColor", theme.grid.toHex()),
            )
            .put(
                "legend",
                JSONObject()
                    .put("type", "scroll")
                    .put("top", 0)
                    .put(
                        "textStyle",
                        JSONObject().put("color", theme.textSecondary.toHex()).put("fontSize", 10),
                    ),
            )
            .put(
                "grid",
                JSONObject()
                    .put("left", 8)
                    .put("right", 8)
                    .put("top", 30)
                    .put("bottom", 4)
                    .put("containLabel", true),
            )
            .put(
                "xAxis",
                JSONObject()
                    .put("type", "category")
                    .put("data", labels)
                    .put("boundaryGap", false)
                    .put("axisLine", JSONObject().put("lineStyle", JSONObject().put("color", theme.axis.toHex())))
                    .put(
                        "axisLabel",
                        JSONObject().put("color", theme.textSecondary.toHex()).put("fontSize", 9),
                    )
                    .put("axisTick", JSONObject().put("show", false)),
            )
            .put(
                "yAxis",
                JSONObject()
                    .put("type", "value")
                    .put("scale", true)
                    .put("splitLine", JSONObject().put("lineStyle", JSONObject().put("color", theme.grid.toHex())))
                    .put(
                        "axisLabel",
                        JSONObject().put("color", theme.textSecondary.toHex()).put("fontSize", 9),
                    ),
            )
            .put("dataZoom", JSONArray().put(JSONObject().put("type", "inside").put("throttle", 50)))
            .put("series", seriesArray)
            .toString()
    }

    fun buildHeatmapOption(panel: UiMetricPanel, theme: ChartTheme): String {
        val rows = panel.heatmap.map { it.row }.distinct()
        val columns = panel.heatmap.map { it.column }.distinct()
        if (rows.isEmpty() || columns.isEmpty()) return "{}"

        val rowIndex = rows.withIndex().associate { (index, row) -> row to index }
        val columnIndex = columns.withIndex().associate { (index, column) -> column to index }
        val values = panel.heatmap.map { it.value }
        val min = values.min()
        val max = values.max()

        val data = JSONArray()
        panel.heatmap.forEach { cell ->
            data.put(
                JSONArray()
                    .put(columnIndex.getValue(cell.column))
                    .put(rowIndex.getValue(cell.row))
                    .put(cell.value),
            )
        }

        return JSONObject()
            .put("backgroundColor", "transparent")
            .put("animation", false)
            .put(
                "tooltip",
                JSONObject()
                    .put("position", "top")
                    .put(
                        "textStyle",
                        JSONObject().put("color", theme.textPrimary.toHex()).put("fontSize", 11),
                    )
                    .put("backgroundColor", theme.background.toHex())
                    .put("borderColor", theme.grid.toHex()),
            )
            .put(
                "grid",
                JSONObject().put("left", 86).put("right", 8).put("top", 8).put("bottom", 44),
            )
            .put(
                "xAxis",
                JSONObject()
                    .put("type", "category")
                    .put("data", JSONArray().apply { columns.forEach { put(it) } })
                    .put("splitArea", JSONObject().put("show", true))
                    .put(
                        "axisLabel",
                        JSONObject().put("color", theme.textSecondary.toHex()).put("fontSize", 9).put("rotate", 30),
                    ),
            )
            .put(
                "yAxis",
                JSONObject()
                    .put("type", "category")
                    .put("data", JSONArray().apply { rows.forEach { put(it) } })
                    .put(
                        "axisLabel",
                        JSONObject().put("color", theme.textSecondary.toHex()).put("fontSize", 10),
                    ),
            )
            .put(
                "visualMap",
                JSONObject()
                    .put("min", min)
                    .put("max", max)
                    .put("calculable", false)
                    .put("orient", "horizontal")
                    .put("left", "center")
                    .put("bottom", 0)
                    .put("textStyle", JSONObject().put("color", theme.textSecondary.toHex()).put("fontSize", 9))
                    .put(
                        "inRange",
                        JSONObject().put(
                            "color",
                            JSONArray()
                                .put(theme.priceDown.toHex())
                                .put(theme.background.toHex())
                                .put(theme.priceUp.toHex()),
                        ),
                    ),
            )
            .put(
                "series",
                JSONArray().put(
                    JSONObject()
                        .put("name", panel.title)
                        .put("type", "heatmap")
                        .put("data", data)
                        .put(
                            "itemStyle",
                            JSONObject()
                                .put("borderColor", theme.background.toHex())
                                .put("borderWidth", 1),
                        ),
                ),
            )
            .toString()
    }

    private fun palette(theme: ChartTheme): List<String> = listOf(
        theme.accent.toHex(),
        theme.priceUp.toHex(),
        theme.priceDown.toHex(),
        theme.warning.toHex(),
        theme.info.toHex(),
        theme.highlight.toHex(),
        theme.flat.toHex(),
    )

    private val MONTH_DAY_FORMAT: DateTimeFormatter = DateTimeFormatter.ofPattern("MM-dd")
    private val YEAR_FORMAT: DateTimeFormatter = DateTimeFormatter.ofPattern("yy-MM-dd")
}
