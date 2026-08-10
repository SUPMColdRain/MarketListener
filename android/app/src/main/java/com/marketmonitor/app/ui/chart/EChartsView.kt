package com.marketmonitor.app.ui.chart

import android.webkit.WebView
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.viewinterop.AndroidView
import com.marketmonitor.app.ui.theme.MarketTheme

/**
 * Controlled offline ECharts surface. The option is embedded as structured
 * JSON (never hand-assembled JS) and the chart is rebuilt on theme/filter
 * changes, so app dark/light always matches the chart.
 */
@Composable
fun EChartsView(
    optionJson: String,
    modifier: Modifier = Modifier,
    height: Dp = MarketTheme.dimensions.chartHeight,
) {
    val theme = rememberChartTheme()
    val heightPx = with(LocalDensity.current) { height.roundToPx() }
    val html = remember(optionJson, theme, heightPx) {
        buildEChartsHtml(optionJson, theme, heightPx)
    }
    AndroidView(
        modifier = modifier.testTag("echarts-chart"),
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
                webView.loadDataWithBaseURL(
                    "file:///android_asset/",
                    html,
                    "text/html",
                    "UTF-8",
                    null,
                )
            }
        },
    )
}

private fun buildEChartsHtml(
    optionJson: String,
    theme: ChartTheme,
    heightPx: Int,
): String {
    val background = theme.background.toHex()
    // Prevent a `</script>` sequence inside a JSON string from closing the
    // script block early; `\/` is valid JSON escaping.
    val safeOption = optionJson.replace("</script", "<\\/script", ignoreCase = true)
    return """
        <!DOCTYPE html>
        <html>
        <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
          html,body{margin:0;padding:0;background:$background}
          #chart{width:100%;height:${heightPx}px}
        </style>
        </head>
        <body>
          <div id="chart"></div>
          <script src="echarts.min.js"></script>
          <script>
            var chart = echarts.init(document.getElementById('chart'));
            chart.setOption($safeOption, true);
            window.addEventListener('resize', function () {
              if (chart) chart.resize();
            });
          </script>
        </body>
        </html>
    """.trimIndent()
}
