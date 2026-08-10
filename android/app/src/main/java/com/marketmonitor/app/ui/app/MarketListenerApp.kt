package com.marketmonitor.app.ui.app

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import com.marketmonitor.app.data.DatabaseFactory
import com.marketmonitor.app.data.ImportedMarketData
import com.marketmonitor.app.data.WatchlistRepository
import com.marketmonitor.app.graph.GraphRepository
import com.marketmonitor.app.graph.GraphSearchState
import com.marketmonitor.app.graph.GraphTab
import com.marketmonitor.app.strategy.ui.PreferencesStrategyHistoryStore
import com.marketmonitor.app.strategy.ui.StrategyTab
import com.marketmonitor.app.strategy.ui.StrategyViewModel
import com.marketmonitor.app.trading.TradingRepository
import com.marketmonitor.app.trading.ui.TradingScreen
import com.marketmonitor.app.ui.DataScreen
import com.marketmonitor.app.ui.market.MarketImportUiState
import com.marketmonitor.app.ui.market.MarketMonitorScreen
import com.marketmonitor.app.ui.settings.SettingsDialog
import com.marketmonitor.app.ui.theme.MarketListenerTheme
import com.marketmonitor.app.ui.theme.ThemeMode
import com.marketmonitor.app.ui.theme.ThemeRepository
import java.io.File
import kotlinx.coroutines.launch

/**
 * Top-level app composable: owns the theme, the five-section navigation and
 * the settings surface. Business operations stay in MainActivity and are
 * passed in as callbacks.
 */
@Composable
fun MarketListenerApp(
    themeRepository: ThemeRepository,
    importState: MarketImportUiState,
    marketData: ImportedMarketData?,
    onImport: (Uri) -> Unit,
    onSyncFromServer: (String) -> Unit,
    activePackageId: String?,
    onCleanColdData: () -> Long,
    graphRepository: GraphRepository?,
    graphState: GraphSearchState,
    onGraphQueryChange: (String) -> Unit,
    onGraphSelectEntity: (String) -> Unit,
    onGraphSelectRelationship: (String) -> Unit,
    onGraphImport: (Uri) -> Unit,
    industryAtlasFile: File?,
) {
    val context = LocalContext.current
    val tradingRepository = remember { TradingRepository(DatabaseFactory.user(context)) }
    val strategyViewModel = remember {
        StrategyViewModel(PreferencesStrategyHistoryStore(context))
    }
    val watchlistRepository = remember { WatchlistRepository(DatabaseFactory.user(context)) }
    val graphPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) onGraphImport(uri)
    }
    var section by rememberSaveable { mutableStateOf(AppSection.MARKET) }
    var settingsOpen by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val themeMode by themeRepository.themeMode.collectAsState(initial = ThemeMode.SYSTEM)

    MarketListenerTheme(themeMode) {
        AppScaffold(
            section = section,
            onSectionChange = { section = it },
            onOpenSettings = { settingsOpen = true },
        ) {
            when (section) {
                AppSection.MARKET -> MarketMonitorScreen(
                    state = importState,
                    marketData = marketData,
                    onImport = onImport,
                    onSyncFromServer = onSyncFromServer,
                    watchlistRepository = watchlistRepository,
                    activePackageId = activePackageId,
                    onCleanColdData = onCleanColdData,
                )
                AppSection.DATA -> DataScreen(marketData)
                AppSection.STRATEGY -> StrategyTab(viewModel = strategyViewModel, marketData = marketData)
                AppSection.STATS -> TradingScreen(tradingRepository, marketData)
                AppSection.INDUSTRY -> GraphTab(
                    repository = graphRepository,
                    state = graphState,
                    onQueryChange = onGraphQueryChange,
                    onSelectEntity = onGraphSelectEntity,
                    onSelectRelationship = onGraphSelectRelationship,
                    onImport = {
                        graphPicker.launch(
                            arrayOf("application/json", "application/octet-stream", "text/plain"),
                        )
                    },
                    industryAtlasFile = industryAtlasFile,
                )
            }
        }
        if (settingsOpen) {
            SettingsDialog(
                current = themeMode,
                onSelect = { mode ->
                    scope.launch { themeRepository.setThemeMode(mode) }
                },
                onDismiss = { settingsOpen = false },
            )
        }
    }
}
