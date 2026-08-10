package com.marketmonitor.app.trading.ui

import android.content.Context
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.VerticalDivider
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.marketmonitor.app.trading.DailyClose
import com.marketmonitor.app.data.ImportedMarketData
import com.marketmonitor.app.trading.FeeInput
import com.marketmonitor.app.trading.NavPoint
import com.marketmonitor.app.trading.PositionView
import com.marketmonitor.app.trading.StrategyEntity
import com.marketmonitor.app.trading.TradeInput
import com.marketmonitor.app.trading.TradeSide
import com.marketmonitor.app.trading.TradeStatus
import com.marketmonitor.app.trading.TradeView
import com.marketmonitor.app.trading.TradingRepository
import com.marketmonitor.app.trading.TradingStatsResult
import com.marketmonitor.app.ui.theme.MarketTheme
import com.marketmonitor.app.ui.theme.MarketType
import com.marketmonitor.app.ui.theme.changeColor
import java.io.File
import kotlinx.coroutines.launch

@Composable
fun TradingScreen(repository: TradingRepository, marketData: ImportedMarketData? = null) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var ui by remember { mutableStateOf(TradingUiState()) }
    var trades by remember { mutableStateOf<List<TradeView>>(emptyList()) }
    var strategies by remember { mutableStateOf<List<StrategyEntity>>(emptyList()) }
    var positions by remember { mutableStateOf<List<PositionView>>(emptyList()) }
    var stats by remember { mutableStateOf<TradingStatsResult?>(null) }
    var prices by remember { mutableStateOf<List<DailyClose>>(emptyList()) }
    val firstInstrument = marketData?.instruments?.firstOrNull()
    val closesFromMarketData = remember(marketData?.packageId) {
        firstInstrument?.candlesByPeriod?.get("1d")?.map { candle ->
            DailyClose(
                epochDay = candle.openTimeSeconds / 86_400L,
                instrumentId = firstInstrument.instrumentId,
                close = candle.close,
            )
        }.orEmpty()
    }
    LaunchedEffect(marketData?.packageId) {
        if (prices.isEmpty() && closesFromMarketData.isNotEmpty()) {
            prices = closesFromMarketData
        }
    }

    suspend fun loadAll() {
        runCatching {
            trades = repository.allTrades()
            strategies = repository.strategies()
            positions = repository.positions()
            stats = repository.stats(prices)
        }.onFailure { ui = ui.copy(error = it.message ?: "加载失败") }
    }

    fun saveDraft(draft: TradeEntryDraft) {
        val errors = draft.errors()
        if (errors.isNotEmpty()) {
            ui = ui.copy(error = errors.joinToString("；"))
            return
        }
        scope.launch {
            ui = ui.copy(error = "")
            runCatching { repository.addTrade(draft.toInput()) }
                .onSuccess { ui = ui.copy(draft = TradeEntryDraft(), selectedTradeId = null, editingTradeId = null); loadAll() }
                .onFailure { ui = ui.copy(error = it.message ?: "保存失败") }
        }
    }

    fun saveRevision(parentTradeId: String, draft: TradeEntryDraft) {
        val errors = draft.errors()
        if (errors.isNotEmpty()) {
            ui = ui.copy(error = errors.joinToString("；"))
            return
        }
        scope.launch {
            ui = ui.copy(error = "")
            runCatching { repository.reviseTrade(parentTradeId, draft.toInput()) }
                .onSuccess { ui = ui.copy(draft = TradeEntryDraft(), selectedTradeId = null, editingTradeId = null); loadAll() }
                .onFailure { ui = ui.copy(error = it.message ?: "修订失败") }
        }
    }

    fun cancelTrade(tradeId: String) {
        scope.launch {
            ui = ui.copy(error = "")
            runCatching { repository.cancelTrade(tradeId) }
                .onSuccess { loadAll() }
                .onFailure { ui = ui.copy(error = it.message ?: "撤销失败") }
        }
    }

    fun beginRevision(view: TradeView) {
        ui = ui.copy(
            draft = draftFromTrade(view),
            selectedTradeId = view.trade.id,
            editingTradeId = view.trade.id,
            error = "",
        )
    }

    val exportLauncher = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/octet-stream")) { uri ->
        if (uri != null && ui.backup.password.isNotBlank()) {
            scope.launch {
                ui = ui.copy(backup = ui.backup.copy(busy = true, message = "", error = ""))
                runCatching { exportToUri(context, repository, ui.backup.password.toCharArray(), uri) }
                    .onSuccess { ui = ui.copy(backup = ui.backup.copy(busy = false, password = "", message = "备份已导出")) }
                    .onFailure { ui = ui.copy(backup = ui.backup.copy(busy = false, password = "", error = it.message ?: "导出失败")) }
            }
        }
    }
    val restoreLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null && ui.backup.password.isNotBlank()) {
            scope.launch {
                ui = ui.copy(backup = ui.backup.copy(busy = true, message = "", error = ""))
                runCatching { restoreFromUri(context, repository, ui.backup.password.toCharArray(), uri) }
                    .onSuccess {
                        ui = ui.copy(backup = ui.backup.copy(busy = false, password = "", message = "恢复完成，共 ${it.counts.values.sum()} 行"))
                        loadAll()
                    }
                    .onFailure { ui = ui.copy(backup = ui.backup.copy(busy = false, password = "", error = it.message ?: "恢复失败")) }
            }
        }
    }

    LaunchedEffect(Unit) { loadAll() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = MarketTheme.dimensions.spacingMedium)
            .padding(vertical = MarketTheme.dimensions.spacingSmall),
        verticalArrangement = Arrangement.spacedBy(MarketTheme.dimensions.spacingSmall),
    ) {
        TabRow(
            selectedTabIndex = ui.tab.ordinal,
            containerColor = MarketTheme.colorScheme.surface,
            contentColor = MarketTheme.colorScheme.primary,
        ) {
            TradingTab.entries.forEachIndexed { index, tab ->
                Tab(
                    selected = ui.tab == tab,
                    onClick = { ui = ui.copy(tab = tab) },
                    text = { Text(tabLabel(tab), style = MarketTheme.typography.labelMedium) },
                )
            }
        }
        if (ui.error.isNotBlank()) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(MarketTheme.dimensions.spacingSmall),
            ) {
                Text(
                    text = "错误：${ui.error}",
                    style = MarketTheme.typography.bodySmall,
                    color = MarketTheme.colors.error,
                    modifier = Modifier.weight(1f),
                )
                TextButton(onClick = { ui = ui.copy(error = "") }) { Text("清除") }
            }
        }
        when (ui.tab) {
            TradingTab.TRADES -> TradesTab(
                ui = ui,
                trades = trades,
                strategies = strategies,
                onUiChange = { ui = it },
                onSaveDraft = ::saveDraft,
                onSaveRevision = ::saveRevision,
                onCancelTrade = ::cancelTrade,
                onBeginRevision = ::beginRevision,
            )
            TradingTab.POSITIONS -> PositionsTab(positions)
            TradingTab.STATS -> StatsTab(stats)
            TradingTab.REVIEW -> ReviewTab(
                stats = stats,
                backup = ui.backup,
                busy = ui.backup.busy,
                onPasswordChange = { ui = ui.copy(backup = ui.backup.copy(password = it)) },
                onExport = {
                    if (ui.backup.password.isBlank()) {
                        ui = ui.copy(error = "请先输入备份密码")
                    } else {
                        ui = ui.copy(error = "")
                        exportLauncher.launch("market-monitor-personal-backup.mmpb")
                    }
                },
                onRestore = {
                    if (ui.backup.password.isBlank()) {
                        ui = ui.copy(error = "请先输入备份密码")
                    } else {
                        ui = ui.copy(error = "")
                        restoreLauncher.launch(arrayOf("application/octet-stream", "application/zip", "*/*"))
                    }
                },
                onDismissMessage = { ui = ui.copy(backup = ui.backup.copy(message = "", error = "")) },
            )
        }
    }
}

@Composable
private fun TradesTab(
    ui: TradingUiState,
    trades: List<TradeView>,
    strategies: List<StrategyEntity>,
    onUiChange: (TradingUiState) -> Unit,
    onSaveDraft: (TradeEntryDraft) -> Unit,
    onSaveRevision: (String, TradeEntryDraft) -> Unit,
    onCancelTrade: (String) -> Unit,
    onBeginRevision: (TradeView) -> Unit,
) {
    LazyColumn(verticalArrangement = Arrangement.spacedBy(MarketTheme.dimensions.spacingSmall)) {
        item {
            EntryForm(
                draft = ui.draft,
                strategies = strategies,
                editingTradeId = ui.editingTradeId,
                onDraftChange = { draft -> onUiChange(ui.withDraft { draft }) },
                onCancelEdit = { onUiChange(ui.copy(draft = TradeEntryDraft(), editingTradeId = null, selectedTradeId = null)) },
            )
        }
        item {
            if (ui.editingTradeId == null) {
                Button(
                    onClick = { onSaveDraft(ui.draft) },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("保存交易") }
            } else {
                Row(horizontalArrangement = Arrangement.spacedBy(MarketTheme.dimensions.spacingSmall), modifier = Modifier.fillMaxWidth()) {
                    Button(
                        onClick = { onSaveRevision(ui.editingTradeId!!, ui.draft) },
                        modifier = Modifier.weight(1f),
                    ) { Text("保存修订") }
                    OutlinedButton(
                        onClick = { onUiChange(ui.copy(draft = TradeEntryDraft(), editingTradeId = null, selectedTradeId = null)) },
                    ) { Text("取消") }
                }
            }
        }
        item { FilterBar(ui.filter) { filter -> onUiChange(ui.withFilter { filter }) } }
        val visibleTrades = trades.filter { ui.filter.matches(it) }
        if (visibleTrades.isEmpty()) {
            item {
                Text(
                    text = "没有匹配的交易记录",
                    style = MarketTheme.typography.bodySmall,
                    color = MarketTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(vertical = MarketTheme.dimensions.spacingMedium),
                )
            }
        } else {
            items(visibleTrades, key = { it.trade.id }) { view ->
                TradeRow(
                    view = view,
                    selected = view.trade.id == ui.selectedTradeId,
                    onSelect = { onUiChange(ui.copy(selectedTradeId = view.trade.id)) },
                    onCancel = { onCancelTrade(view.trade.id) },
                    onRevise = { onBeginRevision(view) },
                )
            }
        }
    }
}

@Composable
private fun EntryForm(
    draft: TradeEntryDraft,
    strategies: List<StrategyEntity>,
    editingTradeId: String?,
    onDraftChange: (TradeEntryDraft) -> Unit,
    onCancelEdit: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(MarketTheme.dimensions.spacingSmall),
        verticalArrangement = Arrangement.spacedBy(MarketTheme.dimensions.spacingSmall),
    ) {
        Text(
            text = if (editingTradeId == null) "录入交易" else "修订交易（原记录保留为已修订）",
            style = MarketTheme.typography.titleSmall,
        )
        OutlinedTextField(
            value = draft.instrumentId,
            onValueChange = { onDraftChange(draft.copy(instrumentId = it)) },
            label = { Text("标的（如 600519.SSE）") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(MarketTheme.dimensions.spacingSmall), modifier = Modifier.fillMaxWidth()) {
            Button(
                onClick = { onDraftChange(draft.copy(side = TradeSide.BUY)) },
                enabled = draft.side != TradeSide.BUY,
            ) { Text("买入") }
            OutlinedButton(
                onClick = { onDraftChange(draft.copy(side = TradeSide.SELL)) },
                enabled = draft.side != TradeSide.SELL,
            ) { Text("卖出") }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(MarketTheme.dimensions.spacingSmall), modifier = Modifier.fillMaxWidth()) {
            OutlinedTextField(
                value = draft.quantity,
                onValueChange = { onDraftChange(draft.copy(quantity = it)) },
                label = { Text("数量") },
                modifier = Modifier.weight(1f),
                singleLine = true,
            )
            OutlinedTextField(
                value = draft.price,
                onValueChange = { onDraftChange(draft.copy(price = it)) },
                label = { Text("价格") },
                modifier = Modifier.weight(1f),
                singleLine = true,
            )
        }
        OutlinedTextField(
            value = draft.executedAt,
            onValueChange = { onDraftChange(draft.copy(executedAt = it)) },
            label = { Text("成交时间（ISO-8601 或毫秒）") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        StrategySelector(
            strategies = strategies,
            selected = draft.strategyId,
            onSelect = { onDraftChange(draft.copy(strategyId = it)) },
        )
        OutlinedTextField(
            value = draft.fees,
            onValueChange = { onDraftChange(draft.copy(fees = it)) },
            label = { Text("费用（类型:金额，逗号分隔，如 COMMISSION:5,STAMP_TAX:1.02）") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
        )
        OutlinedTextField(
            value = draft.note,
            onValueChange = { onDraftChange(draft.copy(note = it)) },
            label = { Text("备注") },
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

@Composable
private fun StrategySelector(
    strategies: List<StrategyEntity>,
    selected: String,
    onSelect: (String) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text("策略归属", style = MarketTheme.typography.labelLarge)
        TextButton(onClick = { expanded = true }) {
            Text(strategies.firstOrNull { it.id == selected }?.name ?: "未指定")
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            DropdownMenuItem(text = { Text("未指定") }, onClick = { onSelect(""); expanded = false })
            strategies.forEach { strategy ->
                DropdownMenuItem(text = { Text(strategy.name) }, onClick = { onSelect(strategy.id); expanded = false })
            }
        }
    }
}

@Composable
private fun FilterBar(filter: TradeFilterState, onFilterChange: (TradeFilterState) -> Unit) {
    Row(horizontalArrangement = Arrangement.spacedBy(MarketTheme.dimensions.spacingSmall), modifier = Modifier.fillMaxWidth()) {
        OutlinedTextField(
            value = filter.instrument,
            onValueChange = { onFilterChange(filter.copy(instrument = it)) },
            label = { Text("筛选标的") },
            modifier = Modifier.weight(1f),
            singleLine = true,
        )
        OutlinedTextField(
            value = filter.strategy,
            onValueChange = { onFilterChange(filter.copy(strategy = it)) },
            label = { Text("筛选策略") },
            modifier = Modifier.weight(1f),
            singleLine = true,
        )
    }
}

@Composable
private fun TradeRow(
    view: TradeView,
    selected: Boolean,
    onSelect: () -> Unit,
    onCancel: () -> Unit,
    onRevise: () -> Unit,
) {
    val trade = view.trade
    val sideColor = if (trade.side == TradeSide.BUY) MarketTheme.colors.priceUp else MarketTheme.colors.priceDown
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = MarketTheme.dimensions.spacingSmall),
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(
                text = "${trade.instrumentId} · ${if (trade.side == TradeSide.BUY) "买入" else "卖出"}",
                style = MarketTheme.typography.labelLarge,
                fontWeight = FontWeight.SemiBold,
                color = sideColor,
            )
            Text(
                text = if (selected) "已选择" else trade.status,
                style = MarketTheme.typography.labelSmall,
                color = if (selected) MarketTheme.colors.info else MarketTheme.colorScheme.onSurfaceVariant,
            )
        }
        Text(
            text = "数量 ${trade.quantity} · 价格 ${trade.price} · 费用 ${view.totalFee}",
            style = MarketTheme.typography.bodySmall,
            color = MarketTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = "时间 ${java.time.Instant.ofEpochMilli(trade.executedAtEpochMillis)}",
            style = MarketTheme.typography.bodySmall,
            color = MarketTheme.colorScheme.onSurfaceVariant,
        )
        if (trade.status == TradeStatus.EXECUTED) {
            Row(horizontalArrangement = Arrangement.spacedBy(MarketTheme.dimensions.spacingSmall)) {
                TextButton(onClick = { onSelect(); onRevise() }) { Text("修订") }
                TextButton(onClick = { onSelect(); onCancel() }) { Text("撤销") }
            }
        }
    }
    HorizontalDivider(color = MarketTheme.colorScheme.outlineVariant)
}

@Composable
private fun PositionsTab(positions: List<PositionView>) {
    if (positions.isEmpty()) {
        Text(
            text = "当前无持仓",
            style = MarketTheme.typography.bodySmall,
            color = MarketTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(vertical = MarketTheme.dimensions.spacingMedium),
        )
        return
    }
    LazyColumn {
        items(positions, key = { it.instrumentId }) { position ->
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = MarketTheme.dimensions.spacingSmall),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                Text(position.instrumentId, style = MarketTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)
                Text(
                    text = "数量 ${position.quantity} · 成本价 ${"%.3f".format(position.averageCost)}",
                    style = MarketTheme.typography.bodySmall,
                    color = MarketTheme.colorScheme.onSurfaceVariant,
                )
                val pnlColor = when {
                    position.realizedPnl > 0 -> MarketTheme.colors.priceUp
                    position.realizedPnl < 0 -> MarketTheme.colors.priceDown
                    else -> MarketTheme.colors.flat
                }
                Text(
                    text = "成本 ${"%.2f".format(position.costBasis)} · 已实现盈亏 ${"%.2f".format(position.realizedPnl)}",
                    style = MarketType.numericSmall,
                    color = pnlColor,
                )
            }
            HorizontalDivider(color = MarketTheme.colorScheme.outlineVariant)
        }
    }
}

@Composable
private fun StatsTab(stats: TradingStatsResult?) {
    if (stats == null) {
        Text(
            text = "暂无统计（需要先录入交易和收盘价）",
            style = MarketTheme.typography.bodySmall,
            color = MarketTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(vertical = MarketTheme.dimensions.spacingMedium),
        )
        return
    }
    LazyColumn(verticalArrangement = Arrangement.spacedBy(MarketTheme.dimensions.spacingSmall)) {
        item {
            Text("核心指标", style = MarketTheme.typography.labelLarge, color = MarketTheme.colorScheme.onSurfaceVariant)
        }
        item { MetricStrip(stats) }
        item { NavChart(stats) }
        item { DrawdownChart(stats) }
        item {
            Text("归因（已实现）", style = MarketTheme.typography.labelLarge, color = MarketTheme.colorScheme.onSurfaceVariant)
        }
        item { AttributionRows(stats.realizedByStrategy, stats.realizedByInstrument) }
        item {
            Text("归因（未实现）", style = MarketTheme.typography.labelLarge, color = MarketTheme.colorScheme.onSurfaceVariant)
        }
        item { AttributionRows(stats.unrealizedByStrategy, stats.unrealizedByInstrument) }
    }
}

@Composable
private fun MetricStrip(stats: TradingStatsResult) {
    val metrics = listOf(
        Triple("总收益率", "${"%.2f".format(stats.totalReturnPct)}%", changeColor(stats.totalReturnPct)),
        Triple("最大回撤", "${"%.2f".format(stats.maxDrawdownPct)}%", MarketTheme.colors.priceDown),
        Triple("胜率", "${"%.1f".format(stats.winRatePct)}%", MarketTheme.colorScheme.onSurface),
        Triple("盈亏比", stats.profitFactor?.let { "%.2f".format(it) } ?: "无亏损样本", MarketTheme.colorScheme.onSurface),
        Triple("平均暴露", "${"%.1f".format(stats.averageExposurePct)}%", MarketTheme.colorScheme.onSurface),
        Triple("最大暴露", "${"%.1f".format(stats.maxExposurePct)}%", MarketTheme.colorScheme.onSurface),
    )
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = MarketTheme.dimensions.spacingSmall),
    ) {
        metrics.chunked(2).forEachIndexed { rowIndex, rowMetrics ->
            Row(modifier = Modifier.fillMaxWidth()) {
                rowMetrics.forEachIndexed { cellIndex, metric ->
                    MetricCell(metric.first, metric.second, metric.third, Modifier.weight(1f))
                    if (cellIndex < rowMetrics.lastIndex) {
                        VerticalDivider(color = MarketTheme.colorScheme.outlineVariant)
                    }
                }
                if (rowMetrics.size == 1) {
                    VerticalDivider(color = MarketTheme.colorScheme.outlineVariant)
                    Box(modifier = Modifier.weight(1f))
                }
            }
            if (rowIndex < metrics.chunked(2).lastIndex) {
                HorizontalDivider(color = MarketTheme.colorScheme.outlineVariant)
            }
        }
    }
}

@Composable
private fun MetricCell(label: String, value: String, valueColor: androidx.compose.ui.graphics.Color, modifier: Modifier = Modifier) {
    Column(modifier = modifier.padding(vertical = MarketTheme.dimensions.spacingSmall)) {
        Text(
            text = label,
            style = MarketTheme.typography.labelSmall,
            color = MarketTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = value,
            style = MarketType.numeric,
            color = valueColor,
        )
    }
}

@Composable
private fun AttributionRows(
    byStrategy: Map<String, Double>,
    byInstrument: Map<String, Double>,
) {
    if (byStrategy.isEmpty() && byInstrument.isEmpty()) {
        Text(
            text = "暂无归因数据",
            style = MarketTheme.typography.bodySmall,
            color = MarketTheme.colorScheme.onSurfaceVariant,
        )
        return
    }
    Column(modifier = Modifier.fillMaxWidth()) {
        byStrategy.toSortedMap().forEach { (key, value) ->
            AttributionRow("策略 $key", value)
            HorizontalDivider(color = MarketTheme.colorScheme.outlineVariant)
        }
        byInstrument.toSortedMap().forEach { (key, value) ->
            AttributionRow("标的 $key", value)
            HorizontalDivider(color = MarketTheme.colorScheme.outlineVariant)
        }
    }
}

@Composable
private fun AttributionRow(label: String, value: Double) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = MarketTheme.dimensions.spacingSmall),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, style = MarketTheme.typography.bodySmall, color = MarketTheme.colorScheme.onSurfaceVariant)
        Text(
            text = "${"%.2f".format(value)}",
            style = MarketType.numericSmall,
            color = changeColor(value),
        )
    }
}

@Composable
private fun NavChart(stats: TradingStatsResult) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Text("净值曲线（含现金）", style = MarketTheme.typography.labelLarge, color = MarketTheme.colorScheme.onSurfaceVariant)
        val points = stats.navCurve
        if (points.size < 2) {
            Text(
                text = "净值数据不足",
                style = MarketTheme.typography.bodySmall,
                color = MarketTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(vertical = MarketTheme.dimensions.spacingMedium),
            )
            return@Column
        }
        LineCanvas(
            values = points.map { it.nav },
            lineColor = MarketTheme.colors.info,
            modifier = Modifier
                .fillMaxWidth()
                .height(MarketTheme.dimensions.chartHeight),
        )
        Text(
            text = "基准 NAV：${"%.2f".format(points.first().nav)} → ${"%.2f".format(points.last().nav)}",
            style = MarketTheme.typography.labelSmall,
            color = MarketTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun DrawdownChart(stats: TradingStatsResult) {
    Column(modifier = Modifier.fillMaxWidth()) {
        Text("回撤曲线（%）", style = MarketTheme.typography.labelLarge, color = MarketTheme.colorScheme.onSurfaceVariant)
        val drawdowns = drawdownSeries(stats.navCurve)
        if (drawdowns.size < 2) {
            Text(
                text = "回撤数据不足",
                style = MarketTheme.typography.bodySmall,
                color = MarketTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(vertical = MarketTheme.dimensions.spacingMedium),
            )
            return@Column
        }
        LineCanvas(
            values = drawdowns,
            lineColor = MarketTheme.colors.priceDown,
            baseline = 0f,
            modifier = Modifier
                .fillMaxWidth()
                .height(MarketTheme.dimensions.chartHeight),
        )
        Text(
            text = "最大回撤：${"%.2f".format(stats.maxDrawdownPct)}%",
            style = MarketTheme.typography.labelSmall,
            color = MarketTheme.colors.priceDown,
        )
    }
}

/** Draws a dense line chart. Values are normalized to the canvas (baseline stays stable). */
@Composable
private fun LineCanvas(
    values: List<Double>,
    lineColor: androidx.compose.ui.graphics.Color,
    modifier: Modifier = Modifier,
    baseline: Float = Float.NaN,
) {
    val gridColor = MarketTheme.colorScheme.outlineVariant
    Canvas(modifier = modifier) {
        val minValue = values.minOrNull() ?: 0.0
        val maxValue = values.maxOrNull() ?: 0.0
        val range = (maxValue - minValue).takeIf { it > 0 } ?: 1.0
        val stepX = if (values.size > 1) size.width / (values.size - 1) else size.width
        val path = Path()
        values.forEachIndexed { index, value ->
            val x = index * stepX
            val normalized = ((value - minValue) / range).toFloat()
            val y = size.height - (normalized * size.height)
            if (index == 0) path.moveTo(x, y) else path.lineTo(x, y)
        }
        drawLine(
            color = gridColor,
            start = Offset(0f, size.height),
            end = Offset(size.width, size.height),
            strokeWidth = 1f,
        )
        drawPath(path, color = lineColor, style = Stroke(width = 3f))
        if (!baseline.isNaN()) {
            val baselineRatio = ((baseline - minValue) / range).toFloat().coerceIn(0f, 1f)
            val y = size.height - (baselineRatio * size.height)
            drawLine(
                color = gridColor,
                start = Offset(0f, y),
                end = Offset(size.width, y),
                strokeWidth = 1f,
            )
        }
    }
}

private fun drawdownSeries(points: List<NavPoint>): List<Double> {
    var peak = Double.NEGATIVE_INFINITY
    return points.map { point ->
        if (point.nav > peak) peak = point.nav
        if (peak > 0.0) (point.nav - peak) / peak * 100.0 else 0.0
    }
}

@Composable
private fun ReviewTab(
    stats: TradingStatsResult?,
    backup: BackupUiState,
    busy: Boolean,
    onPasswordChange: (String) -> Unit,
    onExport: () -> Unit,
    onRestore: () -> Unit,
    onDismissMessage: () -> Unit,
) {
    LazyColumn(verticalArrangement = Arrangement.spacedBy(MarketTheme.dimensions.spacingSmall)) {
        item {
            if (stats != null) {
                NavChart(stats)
            } else {
                Text(
                    text = "暂无净值数据",
                    style = MarketTheme.typography.bodySmall,
                    color = MarketTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(vertical = MarketTheme.dimensions.spacingMedium),
                )
            }
        }
        item {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = MarketTheme.dimensions.spacingSmall),
                verticalArrangement = Arrangement.spacedBy(MarketTheme.dimensions.spacingSmall),
            ) {
                Text("个人数据备份与恢复", style = MarketTheme.typography.titleSmall)
                OutlinedTextField(
                    value = backup.password,
                    onValueChange = onPasswordChange,
                    label = { Text("备份密码") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Row(horizontalArrangement = Arrangement.spacedBy(MarketTheme.dimensions.spacingSmall)) {
                    Button(onClick = onExport, enabled = !busy) { Text("导出加密备份") }
                    OutlinedButton(onClick = onRestore, enabled = !busy) { Text("从备份恢复") }
                }
                if (backup.message.isNotBlank()) {
                    Text(backup.message, style = MarketTheme.typography.bodySmall, color = MarketTheme.colors.priceUp)
                    TextButton(onClick = onDismissMessage) { Text("知道了") }
                }
                if (backup.error.isNotBlank()) {
                    Text(backup.error, style = MarketTheme.typography.bodySmall, color = MarketTheme.colors.error)
                    TextButton(onClick = onDismissMessage) { Text("知道了") }
                }
                Text(
                    text = "恢复过程在事务中完成：任何校验失败都不会改动现有数据。",
                    style = MarketTheme.typography.bodySmall,
                    color = MarketTheme.colorScheme.onSurfaceVariant,
                )
            }
            HorizontalDivider(color = MarketTheme.colorScheme.outlineVariant)
        }
    }
}

private fun tabLabel(tab: TradingTab): String = when (tab) {
    TradingTab.TRADES -> "交易记录"
    TradingTab.POSITIONS -> "持仓"
    TradingTab.STATS -> "统计"
    TradingTab.REVIEW -> "复盘"
}

private fun TradeEntryDraft.toInput(): TradeInput = TradeInput(
    instrumentId = instrumentId.trim(),
    strategyId = strategyId.trim().ifBlank { null },
    side = side,
    quantity = quantity.toLong(),
    price = price.toDouble(),
    executedAtEpochMillis = executedAtEpochMillis()!!,
    note = note.trim().ifBlank { null },
    fees = toFees().map { FeeInput(it.first, it.second) },
)

private suspend fun exportToUri(context: Context, repository: TradingRepository, password: CharArray, uri: Uri) {
    val temp = File(context.cacheDir, "personal-backup-${System.currentTimeMillis()}.mmpb")
    repository.exportBackup(password, temp)
    context.contentResolver.openOutputStream(uri)?.use { output -> temp.inputStream().use { it.copyTo(output) } }
        ?: throw IllegalStateException("无法写入所选文件")
    temp.delete()
}

private suspend fun restoreFromUri(
    context: Context,
    repository: TradingRepository,
    password: CharArray,
    uri: Uri,
): com.marketmonitor.app.trading.RestoreResult {
    val temp = File(context.cacheDir, "personal-restore-${System.currentTimeMillis()}.mmpb")
    context.contentResolver.openInputStream(uri)?.use { input -> temp.outputStream().use(input::copyTo) }
        ?: throw IllegalStateException("无法读取所选文件")
    return try {
        repository.restoreBackup(password, temp)
    } finally {
        temp.delete()
    }
}
