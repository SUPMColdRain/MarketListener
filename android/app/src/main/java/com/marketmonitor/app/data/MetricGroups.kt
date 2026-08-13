package com.marketmonitor.app.data

data class MetricSeries(
    val seriesId: String,
    val metricName: String,
    val latest: MarketMetric,
    val sampleCount: Int,
)

data class MetricGroup(
    val key: String,
    val label: String,
    val series: List<MetricSeries>,
)

private data class GroupRule(
    val key: String,
    val label: String,
    val prefix: String,
)

private val GROUP_RULES = listOf(
    GroupRule("CN_MARGIN", "融资融券（沪/深/京）", "CN_MARGIN"),
    GroupRule("A_SHARE_BREADTH", "A股情绪与市场宽度", "A_SHARE_BREADTH"),
    GroupRule("CN_ZT_POOL", "涨跌停与连板", "CN_ZT_POOL"),
    GroupRule("FUTURES_BREADTH", "期货涨跌家数", "FUTURES_BREADTH"),
    GroupRule("FUTURES_OI_LEADERBOARD", "期货持仓龙虎榜", "FUTURES_OI_LEADERBOARD"),
    GroupRule("FUTURE_GLOBAL_BAR", "外盘期货指标", "FUTURE_GLOBAL_BAR"),
    GroupRule("HSGT_FLOW", "北向/南向资金", "HSGT_FLOW"),
    GroupRule("M1_MONEY_SUPPLY", "宏观·M1货币供应", "M1_MONEY_SUPPLY"),
    GroupRule("M2_MONEY_SUPPLY", "宏观·M2货币供应", "M2_MONEY_SUPPLY"),
    GroupRule("DR007", "宏观·资金利率 DR007", "DR007"),
    GroupRule("CPI", "宏观·通胀 CPI", "CPI"),
    GroupRule("PPI", "宏观·通胀 PPI", "PPI"),
    GroupRule("CPI_PPI_SPREAD", "宏观·CPI-PPI 剪刀差", "CPI_PPI_SPREAD"),
    GroupRule("PMI_MANUFACTURING", "宏观·制造业 PMI", "PMI_MANUFACTURING"),
    GroupRule("PMI_SERVICES", "宏观·服务业 PMI", "PMI_SERVICES"),
    GroupRule("PMI_CAIXIN_MANUFACTURING", "宏观·财新制造业 PMI", "PMI_CAIXIN_MANUFACTURING"),
    GroupRule("PMI_CAIXIN_SERVICES", "宏观·财新服务业 PMI", "PMI_CAIXIN_SERVICES"),
    GroupRule("FED_FUNDS_RATE", "美联储利率", "FED_FUNDS_RATE"),
    GroupRule("USD_INDEX", "美元指数", "USD_INDEX"),
    GroupRule("VIX", "VIX 波动率", "VIX"),
    GroupRule("CN10Y_YIELD", "中国10年期国债收益率", "CN10Y_YIELD"),
    GroupRule("US10Y_YIELD", "美国10年期国债收益率", "US10Y_YIELD"),
    GroupRule("GOLD_SILVER_RATIO", "金银比", "GOLD_SILVER_RATIO"),
    GroupRule("GOLD_OIL_RATIO", "金油比（WTI）", "GOLD_OIL_RATIO"),
    GroupRule("BTC_USD", "比特币", "BTC_USD"),
    GroupRule("ETH_USD", "以太坊", "ETH_USD"),
)

fun groupKeyFor(metricId: String): String {
    val rule = GROUP_RULES.firstOrNull { metricId.startsWith(it.prefix) }
    return rule?.key ?: metricId.substringBefore(':').ifBlank { "OTHER" }
}

fun groupLabelFor(metricId: String): String {
    val rule = GROUP_RULES.firstOrNull { metricId.startsWith(it.prefix) }
    return rule?.label ?: groupKeyFor(metricId)
}

fun seriesIdOf(metric: MarketMetric): String =
    metric.metricId.replace(":${metric.tradingDate}:", ":")

fun aggregateMetrics(metrics: List<MarketMetric>): List<MetricGroup> {
    val buckets = linkedMapOf<String, LinkedHashMap<String, MutableList<MarketMetric>>>()
    for (metric in metrics) {
        val bySeries = buckets.getOrPut(groupKeyFor(metric.metricId)) { linkedMapOf() }
        bySeries.getOrPut(seriesIdOf(metric)) { mutableListOf() }.add(metric)
    }
    val knownOrder = GROUP_RULES.map { it.key }
    return buckets.entries
        .sortedBy { (key, _) ->
            val index = knownOrder.indexOf(key)
            if (index >= 0) index else knownOrder.size
        }
        .map { (key, seriesMap) ->
            val series = seriesMap.map { (seriesId, samples) ->
                val ordered = samples.sortedWith(
                    compareByDescending<MarketMetric> { it.tradingDate }
                        .thenByDescending { it.timestamp }
                        .thenByDescending { it.metricId },
                )
                MetricSeries(
                    seriesId = seriesId,
                    metricName = ordered.first().metricName,
                    latest = ordered.first(),
                    sampleCount = ordered.size,
                )
            }.sortedWith(
                compareByDescending<MetricSeries> { it.latest.tradingDate }.thenBy { it.seriesId },
            )
            MetricGroup(key = key, label = groupLabelFor(key), series = series)
        }
}

fun filterMetrics(metrics: List<MarketMetric>, query: String): List<MarketMetric> {
    val keyword = query.trim()
    if (keyword.isEmpty()) return metrics
    return metrics.filter { metric ->
        metric.metricName.contains(keyword, ignoreCase = true) ||
            metric.metricId.contains(keyword, ignoreCase = true) ||
            metric.instrumentId.contains(keyword, ignoreCase = true) ||
            metric.definition.contains(keyword, ignoreCase = true)
    }
}

fun formatMetricValue(value: Double): String {
    if (value == value.toLong().toDouble()) return value.toLong().toString()
    val text = "%.4f".format(value).trimEnd('0').trimEnd('.')
    return text
}
