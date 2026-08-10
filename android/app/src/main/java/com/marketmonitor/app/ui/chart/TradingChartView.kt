package com.marketmonitor.app.ui.chart

import android.webkit.WebView
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.viewinterop.AndroidView
import com.marketmonitor.app.data.MarketCandle
import com.marketmonitor.app.ui.theme.MarketTheme

/** Theme-aware wrapper around the bundled TradingView lightweight-charts. */
@Composable
fun TradingChartView(
    candles: List<MarketCandle>,
    emptyMessage: String,
    modifier: Modifier = Modifier,
    height: Dp = MarketTheme.dimensions.chartHeight,
) {
    val theme = rememberChartTheme()
    val heightPx = with(LocalDensity.current) { height.roundToPx() }
    val html = remember(candles, theme, emptyMessage, heightPx) {
        buildKlineHtml(candles, theme, emptyMessage, heightPx)
    }
    AndroidView(
        modifier = modifier.testTag("trading-chart"),
        factory = { context ->
            WebView(context).apply {
                settings.javaScriptEnabled = true
                settings.domStorageEnabled = true
                settings.allowFileAccess = true
                settings.blockNetworkLoads = true
            }
        },
        update = { webView ->
            if (webView.tag != html) {
                webView.tag = html
                webView.loadDataWithBaseURL("file:///android_asset/", html, "text/html", "UTF-8", null)
            }
        },
    )
}

/** Builds the current ChartTheme from MarketListener design tokens. */
@Composable
fun rememberChartTheme(): ChartTheme {
    val colors = MarketTheme.colors
    val scheme = MarketTheme.colorScheme
    return remember(colors, scheme) {
        ChartTheme(
            background = scheme.background,
            textPrimary = scheme.onBackground,
            textSecondary = scheme.onSurfaceVariant,
            grid = scheme.outlineVariant,
            axis = scheme.outline,
            accent = scheme.primary,
            priceUp = colors.priceUp,
            priceDown = colors.priceDown,
            flat = colors.flat,
            warning = colors.warning,
            error = colors.error,
            info = colors.info,
            highlight = colors.highlight,
        )
    }
}
