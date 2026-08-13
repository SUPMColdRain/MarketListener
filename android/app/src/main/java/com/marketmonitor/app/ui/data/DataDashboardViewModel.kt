package com.marketmonitor.app.ui.data

import androidx.lifecycle.ViewModel
import com.marketmonitor.app.data.MarketMetric
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Owns the dashboard state and rebuilds it from raw imported metrics. */
class DataDashboardViewModel : ViewModel() {
    private val _state = MutableStateFlow(DataDashboardUiState())
    val state: StateFlow<DataDashboardUiState> = _state.asStateFlow()

    fun refresh(
        metrics: List<MarketMetric>,
        summary: String,
        marketFilter: UiMarketFilter,
        timeRange: UiChartTimeRange,
    ) {
        _state.value = DataDashboardMapper.buildState(metrics, summary, marketFilter, timeRange)
    }
}
