package com.marketmonitor.app.ui.theme

import androidx.compose.ui.unit.dp

/** Density-oriented spacing and sizing shared by all screens. */
data class MarketDimensions(
    val spacingTiny: androidx.compose.ui.unit.Dp = 4.dp,
    val spacingSmall: androidx.compose.ui.unit.Dp = 8.dp,
    val spacingMedium: androidx.compose.ui.unit.Dp = 12.dp,
    val spacingLarge: androidx.compose.ui.unit.Dp = 16.dp,
    val topBarHeight: androidx.compose.ui.unit.Dp = 48.dp,
    val navigationBarHeight: androidx.compose.ui.unit.Dp = 58.dp,
    val chartHeight: androidx.compose.ui.unit.Dp = 240.dp,
    val chartHeightLarge: androidx.compose.ui.unit.Dp = 320.dp,
    val sparklineHeight: androidx.compose.ui.unit.Dp = 28.dp,
    val touchTarget: androidx.compose.ui.unit.Dp = 48.dp,
    val cardPadding: androidx.compose.ui.unit.Dp = 10.dp,
) {
    companion object {
        val Default = MarketDimensions()
    }
}
