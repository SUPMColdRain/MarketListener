package com.marketmonitor.app.ui.chart

import com.marketmonitor.app.data.MarketCandle
import org.json.JSONArray
import org.json.JSONObject

/** Builds the standalone lightweight-charts HTML for one instrument. */
fun buildKlineHtml(
    candles: List<MarketCandle>,
    theme: ChartTheme,
    emptyMessage: String,
    chartHeightPx: Int,
): String {
    val chartData = JSONArray().apply {
        candles.forEach { candle ->
            put(
                JSONObject()
                    .put("time", candle.openTimeSeconds)
                    .put("open", candle.open)
                    .put("high", candle.high)
                    .put("low", candle.low)
                    .put("close", candle.close),
            )
        }
    }
    val background = theme.background.toHex()
    val textColor = theme.textPrimary.toHex()
    val grid = theme.grid.toHex()
    val axis = theme.axis.toHex()
    val up = theme.priceUp.toHex()
    val down = theme.priceDown.toHex()
    val accent = theme.accent.toHex()
    val escapedMessage = escapeHtml(emptyMessage)
    return """
        <html>
        <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
          html,body{margin:0;padding:0;background:$background;color:$textColor;font-family:sans-serif}
          #empty{padding:20px;font-size:12px;color:$axis}
          #chart{height:${chartHeightPx}px;width:100%}
        </style>
        </head>
        <body>
          <div id='empty'>$escapedMessage</div>
          <div id='chart'></div>
          <script src='lightweight-charts.standalone.production.js'></script>
          <script>
            const candles = $chartData;
            if (candles.length) {
              document.getElementById('empty').remove();
              const chart = LightweightCharts.createChart(
                document.getElementById('chart'),
                {
                  layout: { background: { color: '$background' }, textColor: '$textColor' },
                  grid: {
                    vertLines: { color: '$grid' },
                    horzLines: { color: '$grid' },
                  },
                  timeScale: { borderColor: '$axis' },
                  rightPriceScale: { borderColor: '$axis' },
                  crosshair: {
                    vertLine: { color: '$accent', width: 1, style: 3 },
                    horzLine: { color: '$accent', width: 1, style: 3 },
                  },
                  width: window.innerWidth,
                  height: $chartHeightPx,
                },
              );
              const series = chart.addCandlestickSeries({
                upColor: '$up',
                downColor: '$down',
                borderVisible: false,
                wickUpColor: '$up',
                wickDownColor: '$down',
              });
              series.setData(candles);
              chart.timeScale().fitContent();
            }
          </script>
        </body>
        </html>
    """.trimIndent()
}

private fun escapeHtml(value: String): String = value
    .replace("&", "&amp;")
    .replace("<", "&lt;")
    .replace(">", "&gt;")
    .replace("\"", "&quot;")
    .replace("'", "&#39;")
