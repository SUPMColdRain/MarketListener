package com.marketmonitor.app

import android.os.Bundle
import android.os.StatFs
import android.webkit.WebView
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.work.Data
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkInfo
import androidx.work.WorkManager
import com.marketmonitor.app.data.ImportedInstrument
import com.marketmonitor.app.data.ImportedMarketData
import com.marketmonitor.app.data.ImportedMarketDataReader
import com.marketmonitor.app.data.DatabaseFactory
import com.marketmonitor.app.data.DatabaseBoundary
import com.marketmonitor.app.data.MarketCandle
import com.marketmonitor.app.data.MarketPackageImportWorker
import com.marketmonitor.app.data.WatchlistRepository
import com.marketmonitor.app.graph.GraphRepository
import com.marketmonitor.app.graph.GraphSearchState
import com.marketmonitor.app.graph.GraphTab
import com.marketmonitor.app.market.MarketOverview
import com.marketmonitor.app.market.StoragePolicy
import com.marketmonitor.app.strategy.ui.PreferencesStrategyHistoryStore
import com.marketmonitor.app.strategy.ui.StrategyTab
import com.marketmonitor.app.strategy.ui.StrategyViewModel
import com.marketmonitor.app.graph.applyQuery
import com.marketmonitor.app.graph.loaded
import com.marketmonitor.app.graph.selectEntity
import com.marketmonitor.app.graph.selectRelationship
import com.marketmonitor.app.trading.TradingRepository
import com.marketmonitor.app.trading.ui.TradingScreen
import java.io.File
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

class MainActivity : ComponentActivity() {
    private var importState by mutableStateOf(MarketImportUiState())
    private var marketData by mutableStateOf<ImportedMarketData?>(null)
    private var graphRepository by mutableStateOf<GraphRepository?>(null)
    private var graphState by mutableStateOf(GraphSearchState())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        importState = restoredImportState()
        refreshMarketData()
        refreshGraphSnapshot()
        enableEdgeToEdge()
        setContent {
            MaterialTheme {
                val tradingRepository = remember { TradingRepository(DatabaseFactory.user(applicationContext)) }
                val strategyViewModel = remember {
                    StrategyViewModel(PreferencesStrategyHistoryStore(applicationContext))
                }
                val watchlistRepository = remember { WatchlistRepository(DatabaseFactory.user(applicationContext)) }
                val graphPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
                    if (uri != null) enqueueGraphImport(uri)
                }
                var activeSection by remember { mutableStateOf(0) }
                Column(modifier = Modifier.fillMaxSize().statusBarsPadding()) {
                    TabRow(selectedTabIndex = activeSection) {
                        Tab(selected = activeSection == 0, onClick = { activeSection = 0 }, text = { Text("行情") })
                        Tab(selected = activeSection == 1, onClick = { activeSection = 1 }, text = { Text("交易") })
                        Tab(selected = activeSection == 2, onClick = { activeSection = 2 }, text = { Text("图谱") })
                        Tab(selected = activeSection == 3, onClick = { activeSection = 3 }, text = { Text("策略") })
                    }
                    when (activeSection) {
                        0 -> MarketMonitorScreen(
                            state = importState,
                            marketData = marketData,
                            onImport = ::enqueueImport,
                            watchlistRepository = watchlistRepository,
                            activePackageId = marketData?.packageId,
                            onCleanColdData = {
                                val coldRoot = DatabaseBoundary.coldDirectory(applicationContext)
                                val availableBytes = runCatching { StatFs(coldRoot.absolutePath).availableBytes }
                                    .getOrDefault(Long.MAX_VALUE)
                                StoragePolicy.cleanup(
                                    coldRoot = coldRoot.toPath(),
                                    activePackageIds = setOfNotNull(marketData?.packageId),
                                    availableBytes = availableBytes,
                                    reserveBytes = 64L * 1024L * 1024L,
                                ).freedBytes
                            },
                        )
                        1 -> TradingScreen(tradingRepository, marketData)
                        2 -> GraphTab(
                            repository = graphRepository,
                            state = graphState,
                            onQueryChange = { keyword -> graphState = graphState.applyQuery(graphRepository, keyword) },
                            onSelectEntity = { entityId -> graphState = graphState.selectEntity(graphRepository, entityId) },
                            onSelectRelationship = { relationshipId ->
                                graphState = graphState.selectRelationship(graphRepository, relationshipId)
                            },
                            onImport = {
                                graphPicker.launch(arrayOf("application/json", "application/octet-stream", "text/plain"))
                            },
                        )
                        3 -> StrategyTab(viewModel = strategyViewModel, marketData = marketData)
                        else -> Unit
                    }
                }
            }
        }
    }

    private fun enqueueImport(uri: android.net.Uri) {
        importState = MarketImportUiState(dataStatus = "正在读取所选行情包")
        Thread {
            try {
                val target = File(cacheDir, "selected-market-package.zip")
                contentResolver.openInputStream(uri)?.use { input -> target.outputStream().use(input::copyTo) }
                    ?: throw IllegalArgumentException("无法读取所选文件")
                val request = OneTimeWorkRequestBuilder<MarketPackageImportWorker>()
                    .setInputData(Data.Builder().putString("package_path", target.path).build())
                    .build()
                runOnUiThread {
                    importState = MarketImportUiState(dataStatus = "行情包已加入队列，正在验证")
                    val workManager = WorkManager.getInstance(this)
                    workManager.enqueue(request)
                    workManager.getWorkInfoByIdLiveData(request.id).observe(this) { info ->
                        if (info != null) {
                            importState = stateForWork(info)
                            if (info.state == WorkInfo.State.SUCCEEDED) refreshMarketData()
                        }
                    }
                }
            } catch (_: Exception) {
                runOnUiThread { importState = MarketImportUiState(dataStatus = "读取行情包失败") }
            }
        }.start()
    }

    private fun restoredImportState(): MarketImportUiState {
        val preferences = getSharedPreferences("market-package", MODE_PRIVATE)
        val packageId = preferences.getString("active", null) ?: return MarketImportUiState()
        val cutoff = preferences.getString("active_cutoff", null) ?: "未记录"
        return MarketImportUiState(
            dataStatus = "已启用已验证行情包：$packageId",
            cutoff = cutoff,
            sourceAndQuality = "签名、哈希和载荷校验已通过",
            hasImportedMarketData = true,
        )
    }

    private fun refreshMarketData() {
        Thread {
            val snapshot = try {
                ImportedMarketDataReader(this).readActive()
            } catch (_: Exception) {
                null
            }
            runOnUiThread { marketData = snapshot }
        }.start()
    }

    private fun enqueueGraphImport(uri: android.net.Uri) {
        Thread {
            try {
                val target = File(filesDir, "graph-snapshot.json")
                contentResolver.openInputStream(uri)?.use { input -> target.outputStream().use(input::copyTo) }
                    ?: throw IllegalArgumentException("无法读取所选文件")
                runOnUiThread { refreshGraphSnapshot() }
            } catch (_: Exception) {
                runOnUiThread { graphState = graphState.copy(error = "导入图谱快照失败") }
            }
        }.start()
    }

    private fun refreshGraphSnapshot() {
        Thread {
            val repository = try {
                val file = File(filesDir, "graph-snapshot.json")
                if (file.isFile) GraphRepository.fromJson(file.readText()) else null
            } catch (_: Exception) {
                null
            }
            runOnUiThread {
                graphRepository = repository
                graphState = graphState.loaded(repository)
            }
        }.start()
    }
}

@Composable
private fun MarketMonitorScreen(
    state: MarketImportUiState,
    marketData: ImportedMarketData?,
    onImport: (android.net.Uri) -> Unit,
    watchlistRepository: WatchlistRepository,
    activePackageId: String?,
    onCleanColdData: () -> Long,
) {
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) onImport(uri)
    }
    var cleanedBytes by remember { mutableStateOf<Long?>(null) }
    val overview = remember(marketData) { MarketOverview.compute(marketData) }
    Column(
        modifier = Modifier.fillMaxSize().statusBarsPadding().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("行情监控", style = MaterialTheme.typography.titleLarge)
            Button(onClick = { picker.launch(arrayOf("application/zip", "application/octet-stream")) }) { Text("导入行情包") }
        }
        StatusCard("数据状态", state.dataStatus)
        StatusCard("数据截止时间", state.cutoff)
        StatusCard("来源与质量", state.sourceAndQuality)
        OverviewCard(overview)
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            TextButton(onClick = { cleanedBytes = onCleanColdData() }) { Text("清理冷数据") }
            cleanedBytes?.let { Text("已释放 ${it / 1024} KB") }
        }
        ImportedMarketContent(marketData, state.hasImportedMarketData, watchlistRepository)
    }
}

@Composable
private fun ImportedMarketContent(
    marketData: ImportedMarketData?,
    hasImportedMarketData: Boolean,
    watchlistRepository: WatchlistRepository,
) {
    val instruments = marketData?.instruments.orEmpty()
    val scope = rememberCoroutineScope()
    var watchlistIds by remember { mutableStateOf<List<String>>(emptyList()) }
    LaunchedEffect(marketData?.packageId) { watchlistIds = watchlistRepository.all() }
    var selectedInstrumentId by remember(marketData?.packageId) { mutableStateOf(instruments.firstOrNull()?.instrumentId) }
    val selectedInstrument = instruments.firstOrNull { it.instrumentId == selectedInstrumentId } ?: instruments.firstOrNull()
    var selectedPeriod by remember(selectedInstrument?.instrumentId) {
        mutableStateOf(preferredPeriod(selectedInstrument))
    }
    val periods = selectedInstrument?.candlesByPeriod?.keys.orEmpty().toList()
    val activePeriod = selectedPeriod.takeIf { it in periods } ?: periods.firstOrNull().orEmpty()
    val candles = selectedInstrument?.candlesByPeriod?.get(activePeriod).orEmpty()

    Text("K 线图", style = MaterialTheme.typography.titleMedium)
    if (instruments.isNotEmpty() && selectedInstrument != null) {
        InstrumentSelector(instruments, selectedInstrument.instrumentId) { selectedInstrumentId = it }
        val inWatchlist = selectedInstrument.instrumentId in watchlistIds
        TextButton(
            onClick = {
                scope.launch {
                    if (inWatchlist) {
                        watchlistRepository.remove(selectedInstrument.instrumentId)
                    } else {
                        watchlistRepository.add(selectedInstrument.instrumentId)
                    }
                    watchlistIds = watchlistRepository.all()
                }
            },
        ) {
            Text(if (inWatchlist) "移出自选" else "加入自选")
        }
        if (watchlistIds.isNotEmpty()) {
            Text("自选（${watchlistIds.size}）：${watchlistIds.joinToString("、")}", style = MaterialTheme.typography.labelMedium)
        }
        if (periods.isNotEmpty()) {
            TabRow(selectedTabIndex = periods.indexOf(activePeriod).coerceAtLeast(0)) {
                periods.forEach { period ->
                    Tab(selected = period == activePeriod, onClick = { selectedPeriod = period }, text = { Text(period) })
                }
            }
        }
        StatusCard("当前数据", "${selectedInstrument.label}，$activePeriod，${candles.size} 根")
        val sources = candles.map { it.source }.distinct().joinToString("、")
        val quality = candles.map { it.qualityStatus }.distinct().joinToString("、")
        StatusCard("当前来源与质量", "来源：$sources；质量：$quality")
    }
    OfflineKline(candles, hasImportedMarketData)
}

@Composable
private fun OverviewCard(overview: MarketOverview) {
    val details = if (overview.packageId == null) {
        "无已导入行情数据（不显示为零或正常）"
    } else {
        val staleText = if (overview.stale) "数据可能已陈旧" else "数据在阈值内"
        "标的 ${overview.instruments.size}，K线 ${overview.totalCandles}，异常标的 ${overview.anomalyCount}；$staleText"
    }
    StatusCard("市场概览", details)
}

@Composable
private fun InstrumentSelector(
    instruments: List<ImportedInstrument>,
    selectedInstrumentId: String,
    onSelect: (String) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    val selected = instruments.firstOrNull { it.instrumentId == selectedInstrumentId } ?: instruments.first()
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text("样本标的", style = MaterialTheme.typography.labelLarge)
        Box {
            TextButton(onClick = { expanded = true }) { Text(selected.label) }
            DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                instruments.forEach { instrument ->
                    DropdownMenuItem(
                        text = { Text(instrument.label) },
                        onClick = { onSelect(instrument.instrumentId); expanded = false },
                    )
                }
            }
        }
    }
}

@Composable
private fun StatusCard(title: String, value: String) {
    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(title, style = MaterialTheme.typography.labelLarge)
            Text(value, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
private fun OfflineKline(candles: List<MarketCandle>, hasImportedMarketData: Boolean) {
    val emptyMessage = if (hasImportedMarketData) "行情包已导入，但当前标的没有可显示的 K 线" else "尚未导入行情数据"
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
    val html = """<html><body style='margin:0;background:#101418;color:#d5dde5;font-family:sans-serif'><div id='empty' style='padding:24px'>$emptyMessage</div><div id='chart' style='height:100%'></div><script src='lightweight-charts.standalone.production.js'></script><script>const candles=$chartData;if(candles.length){document.getElementById('empty').remove();const chart=LightweightCharts.createChart(document.getElementById('chart'),{layout:{background:{color:'#101418'},textColor:'#d5dde5'},width:window.innerWidth,height:280});const series=chart.addCandlestickSeries({upColor:'#1b9e77',downColor:'#d1495b',borderVisible:false,wickUpColor:'#1b9e77',wickDownColor:'#d1495b'});series.setData(candles);chart.timeScale().fitContent();}</script></body></html>"""
    AndroidView(
        modifier = Modifier.fillMaxWidth().height(280.dp),
        factory = { context -> WebView(context).apply {
            settings.javaScriptEnabled = true
            settings.allowFileAccess = true
            settings.blockNetworkLoads = true
        } },
        update = { webView -> webView.loadDataWithBaseURL("file:///android_asset/", html, "text/html", "UTF-8", null) },
    )
}

private data class MarketImportUiState(
    val dataStatus: String = "尚未导入已验证行情包",
    val cutoff: String = "暂无已验证数据截止时间",
    val sourceAndQuality: String = "导入成功后显示校验结果",
    val hasImportedMarketData: Boolean = false,
)

private fun stateForWork(info: WorkInfo): MarketImportUiState = when (info.state) {
    WorkInfo.State.ENQUEUED -> MarketImportUiState(dataStatus = "行情包已加入队列，等待验证")
    WorkInfo.State.RUNNING -> MarketImportUiState(dataStatus = "正在验证签名、哈希和数据载荷")
    WorkInfo.State.SUCCEEDED -> MarketImportUiState(
        dataStatus = "行情包已验证并导入：${info.outputData.getString(MarketPackageImportWorker.RESULT_PACKAGE_ID) ?: "未命名"}",
        cutoff = info.outputData.getString(MarketPackageImportWorker.RESULT_DATA_CUTOFF) ?: "未记录",
        sourceAndQuality = "签名、哈希和载荷校验已通过",
        hasImportedMarketData = true,
    )
    WorkInfo.State.FAILED -> MarketImportUiState(dataStatus = "导入失败：${validationErrorText(info.outputData.getString(MarketPackageImportWorker.RESULT_ERROR))}")
    WorkInfo.State.CANCELLED -> MarketImportUiState(dataStatus = "导入任务已取消")
    WorkInfo.State.BLOCKED -> MarketImportUiState(dataStatus = "导入任务被阻塞")
}

private fun validationErrorText(value: String?): String = when (value) {
    "SIGNATURE" -> "签名校验未通过"
    "HASH" -> "文件哈希校验未通过"
    "SCHEMA" -> "行情包结构版本不受支持"
    "SPACE" -> "设备可用空间不足"
    "DUPLICATE" -> "该行情包已导入"
    "DOWNGRADE" -> "行情包要求更高版本的 App"
    "PAYLOAD" -> "行情数据载荷校验未通过"
    else -> "行情包结构无效"
}

private fun preferredPeriod(instrument: ImportedInstrument?): String = when {
    instrument == null -> ""
    "1d" in instrument.candlesByPeriod -> "1d"
    else -> instrument.candlesByPeriod.keys.firstOrNull().orEmpty()
}
