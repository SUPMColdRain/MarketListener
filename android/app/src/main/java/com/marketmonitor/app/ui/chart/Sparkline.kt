package com.marketmonitor.app.ui.chart

import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import com.marketmonitor.app.ui.data.UiMetricPoint
import com.marketmonitor.app.ui.theme.MarketTheme

/** Dense native sparkline for lists and rankings; colors follow MarketTheme. */
@Composable
fun Sparkline(
    points: List<UiMetricPoint>,
    modifier: Modifier = Modifier,
    color: Color? = null,
    strokeWidthPx: Float = 1.8f,
) {
    val resolvedColor = color ?: when {
        points.isEmpty() -> MarketTheme.colors.flat
        points.last().value >= points.first().value -> MarketTheme.colors.priceUp
        else -> MarketTheme.colors.priceDown
    }
    Canvas(modifier = modifier) {
        if (points.size < 2) return@Canvas
        val min = points.minOf { it.value }
        val max = points.maxOf { it.value }
        val range = (max - min).takeIf { it > 0.0 } ?: 1.0
        val stepX = size.width / (points.size - 1)
        val path = Path()
        points.forEachIndexed { index, point ->
            val x = index * stepX
            val y = size.height - ((point.value - min) / range * size.height).toFloat()
            if (index == 0) path.moveTo(x, y) else path.lineTo(x, y)
        }
        drawPath(path, color = resolvedColor, style = Stroke(width = strokeWidthPx))
        drawCircle(
            color = resolvedColor,
            radius = 1.6f,
            center = Offset(size.width, size.height - ((points.last().value - min) / range * size.height).toFloat()),
        )
    }
}
