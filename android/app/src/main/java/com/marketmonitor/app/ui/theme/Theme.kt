package com.marketmonitor.app.ui.theme

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.graphics.Color
import androidx.core.view.WindowCompat

private val LocalMarketColors = staticCompositionLocalOf { MarketColors.Dark }
private val LocalMarketDimensions = staticCompositionLocalOf { MarketDimensions.Default }
private val LocalIsDark = staticCompositionLocalOf { true }

/** Read-only access to the MarketListener design tokens inside composition. */
object MarketTheme {
    val colors: MarketColors
        @Composable @ReadOnlyComposable get() = LocalMarketColors.current

    val dimensions: MarketDimensions
        @Composable @ReadOnlyComposable get() = LocalMarketDimensions.current

    val isDark: Boolean
        @Composable @ReadOnlyComposable get() = LocalIsDark.current

    val colorScheme: androidx.compose.material3.ColorScheme
        @Composable @ReadOnlyComposable get() = MaterialTheme.colorScheme

    val typography: androidx.compose.material3.Typography
        @Composable @ReadOnlyComposable get() = MaterialTheme.typography

    val shapes: androidx.compose.material3.Shapes
        @Composable @ReadOnlyComposable get() = MaterialTheme.shapes
}

/** Single entry point wrapping the whole app. */
@Composable
fun MarketListenerTheme(
    themeMode: ThemeMode,
    content: @Composable () -> Unit,
) {
    val dark = resolveIsDark(themeMode, isSystemInDarkTheme())
    val colorScheme = if (dark) DarkColorScheme else LightColorScheme
    val marketColors = if (dark) MarketColors.Dark else MarketColors.Light
    val view = LocalView.current
    val context = LocalContext.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (context as? Activity)?.window ?: return@SideEffect
            WindowCompat.getInsetsController(window, view).apply {
                isAppearanceLightStatusBars = !dark
                isAppearanceLightNavigationBars = !dark
            }
        }
    }
    CompositionLocalProvider(
        LocalMarketColors provides marketColors,
        LocalMarketDimensions provides MarketDimensions.Default,
        LocalIsDark provides dark,
    ) {
        MaterialTheme(
            colorScheme = colorScheme,
            typography = MarketType.typography,
            shapes = MarketShapes.shapes,
            content = content,
        )
    }
}

/** Pure resolution of the effective dark flag; kept testable without a device. */
fun resolveIsDark(themeMode: ThemeMode, systemInDark: Boolean): Boolean = when (themeMode) {
    ThemeMode.SYSTEM -> systemInDark
    ThemeMode.LIGHT -> false
    ThemeMode.DARK -> true
}

/** Convenience: status color for a signed change (positive/negative/flat). */
@Composable
fun changeColor(value: Double): Color = when {
    value > 0 -> MarketTheme.colors.priceUp
    value < 0 -> MarketTheme.colors.priceDown
    else -> MarketTheme.colors.flat
}
