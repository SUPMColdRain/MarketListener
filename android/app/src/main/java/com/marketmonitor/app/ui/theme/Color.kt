package com.marketmonitor.app.ui.theme

import androidx.compose.material3.ColorScheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.graphics.Color

/**
 * Fixed financial-terminal palettes. Dynamic Color is intentionally disabled:
 * MarketListener needs stable brand and market-status colors on every device.
 */
object MarketPalette {
    // Dark
    val DarkBackground = Color(0xFF0B0E14)
    val DarkSurface = Color(0xFF10151E)
    val DarkSurfaceElevated = Color(0xFF151C27)
    val DarkSurfaceSelected = Color(0xFF1B2534)
    val DarkDivider = Color(0xFF232D3D)
    val DarkPrimaryText = Color(0xFFE8EDF5)
    val DarkSecondaryText = Color(0xFF929EAF)
    val DarkDisabledText = Color(0xFF586273)
    val AccentBlue = Color(0xFF2962FF)

    // Light
    val LightBackground = Color(0xFFF5F7FA)
    val LightSurface = Color(0xFFFFFFFF)
    val LightSurfaceElevated = Color(0xFFF0F3F8)
    val LightSurfaceSelected = Color(0xFFE3EAF6)
    val LightDivider = Color(0xFFE1E6EE)
    val LightPrimaryText = Color(0xFF11151C)
    val LightSecondaryText = Color(0xFF687386)
    val LightDisabledText = Color(0xFFA6AFBD)
}

val DarkColorScheme: ColorScheme = darkColorScheme(
    primary = MarketPalette.AccentBlue,
    onPrimary = Color.White,
    primaryContainer = Color(0xFF1B2A4A),
    onPrimaryContainer = Color(0xFFBCCDFF),
    secondary = MarketPalette.DarkSecondaryText,
    onSecondary = MarketPalette.DarkBackground,
    secondaryContainer = Color(0xFF1B2534),
    onSecondaryContainer = MarketPalette.DarkPrimaryText,
    tertiary = Color(0xFF4DA3FF),
    onTertiary = MarketPalette.DarkBackground,
    background = MarketPalette.DarkBackground,
    onBackground = MarketPalette.DarkPrimaryText,
    surface = MarketPalette.DarkSurface,
    onSurface = MarketPalette.DarkPrimaryText,
    surfaceVariant = MarketPalette.DarkSurfaceElevated,
    onSurfaceVariant = MarketPalette.DarkSecondaryText,
    surfaceContainer = MarketPalette.DarkSurfaceElevated,
    surfaceContainerHigh = MarketPalette.DarkSurfaceSelected,
    surfaceContainerHighest = MarketPalette.DarkSurfaceSelected,
    surfaceContainerLow = MarketPalette.DarkSurface,
    surfaceContainerLowest = MarketPalette.DarkBackground,
    surfaceTint = MarketPalette.AccentBlue,
    outline = MarketPalette.DarkDivider,
    outlineVariant = MarketPalette.DarkDivider,
    error = Color(0xFFFF6B6B),
    onError = MarketPalette.DarkBackground,
    errorContainer = Color(0xFF4A1F24),
    onErrorContainer = Color(0xFFFFC9C9),
    inverseSurface = MarketPalette.DarkPrimaryText,
    inverseOnSurface = MarketPalette.DarkBackground,
    inversePrimary = Color(0xFF5B86FF),
)

val LightColorScheme: ColorScheme = lightColorScheme(
    primary = MarketPalette.AccentBlue,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFDCE6FF),
    onPrimaryContainer = Color(0xFF10327A),
    secondary = MarketPalette.LightSecondaryText,
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFE3EAF6),
    onSecondaryContainer = MarketPalette.LightPrimaryText,
    tertiary = Color(0xFF2563EB),
    onTertiary = Color.White,
    background = MarketPalette.LightBackground,
    onBackground = MarketPalette.LightPrimaryText,
    surface = MarketPalette.LightSurface,
    onSurface = MarketPalette.LightPrimaryText,
    surfaceVariant = MarketPalette.LightSurfaceElevated,
    onSurfaceVariant = MarketPalette.LightSecondaryText,
    surfaceContainer = MarketPalette.LightSurfaceElevated,
    surfaceContainerHigh = MarketPalette.LightSurfaceSelected,
    surfaceContainerHighest = MarketPalette.LightSurfaceSelected,
    surfaceContainerLow = MarketPalette.LightSurface,
    surfaceContainerLowest = Color.White,
    surfaceTint = MarketPalette.AccentBlue,
    outline = MarketPalette.LightDivider,
    outlineVariant = MarketPalette.LightDivider,
    error = Color(0xFFC62828),
    onError = Color.White,
    errorContainer = Color(0xFFFFDAD6),
    onErrorContainer = Color(0xFF410002),
    inverseSurface = MarketPalette.LightPrimaryText,
    inverseOnSurface = MarketPalette.LightSurface,
    inversePrimary = Color(0xFFBCCDFF),
)
