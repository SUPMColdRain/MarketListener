package com.marketmonitor.app.ui.chart

import androidx.compose.ui.graphics.Color

/** Colors shared by every chart surface (WebView or Canvas). */
data class ChartTheme(
    val background: Color,
    val textPrimary: Color,
    val textSecondary: Color,
    val grid: Color,
    val axis: Color,
    val accent: Color,
    val priceUp: Color,
    val priceDown: Color,
    val flat: Color,
    val warning: Color,
    val error: Color,
    val info: Color,
    val highlight: Color,
) {
    companion object {
        fun from(
            background: Color,
            textPrimary: Color,
            textSecondary: Color,
            grid: Color,
            axis: Color,
            accent: Color,
            priceUp: Color,
            priceDown: Color,
            flat: Color,
            warning: Color,
            error: Color,
            info: Color,
            highlight: Color,
        ): ChartTheme = ChartTheme(
            background = background,
            textPrimary = textPrimary,
            textSecondary = textSecondary,
            grid = grid,
            axis = axis,
            accent = accent,
            priceUp = priceUp,
            priceDown = priceDown,
            flat = flat,
            warning = warning,
            error = error,
            info = info,
            highlight = highlight,
        )
    }
}

/** Converts a Compose color to the `#rrggbb` form used by JS charts. */
fun Color.toHex(): String {
    val red = (red * 255).toInt().coerceIn(0, 255)
    val green = (green * 255).toInt().coerceIn(0, 255)
    val blue = (blue * 255).toInt().coerceIn(0, 255)
    return "#%02x%02x%02x".format(red, green, blue)
}
