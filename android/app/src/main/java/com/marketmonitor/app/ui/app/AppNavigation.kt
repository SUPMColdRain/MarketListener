package com.marketmonitor.app.ui.app

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.AccountTree
import androidx.compose.material.icons.outlined.Analytics
import androidx.compose.material.icons.outlined.BarChart
import androidx.compose.material.icons.outlined.Bolt
import androidx.compose.material.icons.automirrored.outlined.ShowChart
import androidx.compose.ui.graphics.vector.ImageVector

/** The five first-level sections of MarketListener. */
enum class AppSection(
    val label: String,
    val icon: ImageVector,
) {
    MARKET("行情", Icons.AutoMirrored.Outlined.ShowChart),
    DATA("数据", Icons.Outlined.Analytics),
    STRATEGY("策略", Icons.Outlined.Bolt),
    STATS("统计", Icons.Outlined.BarChart),
    INDUSTRY("产业链", Icons.Outlined.AccountTree),
}
