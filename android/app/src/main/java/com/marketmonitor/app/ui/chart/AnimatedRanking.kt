@file:OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)

package com.marketmonitor.app.ui.chart

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.background
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.marketmonitor.app.data.formatMetricValue
import com.marketmonitor.app.ui.data.UiRankingFrame
import com.marketmonitor.app.ui.theme.MarketType
import com.marketmonitor.app.ui.theme.MarketTheme
import com.marketmonitor.app.ui.theme.changeColor
import kotlinx.coroutines.delay

/**
 * Native ranking browser. It only animates the transition between real
 * timestamped frames; it never invents intermediate values.
 */
@Composable
fun AnimatedRanking(
    frames: List<UiRankingFrame>,
    modifier: Modifier = Modifier,
) {
    if (frames.isEmpty()) {
        Text(
            "暂无该指标数据",
            style = MaterialTheme.typography.bodyMedium,
            color = MarketTheme.colors.flat,
            modifier = Modifier.padding(vertical = 12.dp),
        )
        return
    }

    var selectedIndex by remember(frames) { mutableIntStateOf(0) }
    var playing by remember(frames) { mutableStateOf(false) }
    val listState = rememberLazyListState()

    LaunchedEffect(playing, frames.size) {
        if (playing && frames.size > 1) {
            while (true) {
                delay(1_500)
                selectedIndex = (selectedIndex + 1) % frames.size
            }
        }
    }

    Column(modifier = modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            LazyRow(
                modifier = Modifier.weight(1f),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                items(frames, key = { it.dateLabel }) { frame ->
                    FilterChip(
                        selected = frame.dateLabel == frames[selectedIndex].dateLabel,
                        onClick = {
                            playing = false
                            selectedIndex = frames.indexOfFirst { it.dateLabel == frame.dateLabel }
                                .coerceAtLeast(0)
                        },
                        label = { Text(frame.dateLabel, style = MaterialTheme.typography.labelSmall) },
                    )
                }
            }
            if (frames.size > 1) {
                IconButton(onClick = { playing = !playing }) {
                    Icon(
                        imageVector = if (playing) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                        contentDescription = if (playing) "暂停排名播放" else "播放排名",
                        tint = MarketTheme.colorScheme.primary,
                    )
                }
            }
        }

        val frame = frames[selectedIndex]
        val maxValue = frame.items.maxOfOrNull { it.value }
        LazyColumn(
            state = listState,
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(max = 480.dp),
            userScrollEnabled = false,
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            items(frame.items, key = { it.key }) { item ->
                RankingRow(
                    modifier = Modifier.animateItemPlacement(),
                    rank = frame.items.indexOfFirst { it.key == item.key } + 1,
                    label = item.label,
                    value = item.value,
                    changePct = item.changePct,
                    maxValue = maxValue,
                )
            }
        }
    }
}

@Composable
private fun RankingRow(
    modifier: Modifier = Modifier,
    rank: Int,
    label: String,
    value: Double,
    changePct: Double?,
    maxValue: Double?,
) {
    val fraction = if (maxValue != null && maxValue > 0.0) {
        (value / maxValue).coerceIn(0.02, 1.0).toFloat()
    } else {
        0.02f
    }
    Row(
        modifier = modifier
            .fillMaxWidth()
            .height(44.dp)
            .padding(horizontal = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = rank.toString().padStart(2, '0'),
            style = MarketType.code,
            color = MarketTheme.colors.flat,
            modifier = Modifier.padding(end = 8.dp),
        )
        Column(modifier = Modifier.weight(1f)) {
            Row(modifier = Modifier.fillMaxWidth()) {
                Text(
                    text = label,
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.Medium,
                    color = MaterialTheme.colorScheme.onSurface,
                    modifier = Modifier.weight(1f),
                    maxLines = 1,
                )
                Text(
                    text = formatMetricValue(value),
                    style = MarketType.numericSmall,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                changePct?.let {
                    Text(
                        text = (if (it >= 0) "+" else "") + "%.2f%%".format(it),
                        style = MarketType.numericSmall,
                        color = changeColor(it),
                        modifier = Modifier.padding(start = 8.dp),
                    )
                }
            }
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 4.dp)
                    .height(3.dp)
                    .background(MarketTheme.colorScheme.surfaceVariant),
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth(fraction)
                        .fillMaxHeight()
                        .background(MarketTheme.colorScheme.primary),
                )
            }
        }
    }
}
