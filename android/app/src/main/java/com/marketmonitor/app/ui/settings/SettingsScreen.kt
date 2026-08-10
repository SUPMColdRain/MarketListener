package com.marketmonitor.app.ui.settings

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import com.marketmonitor.app.ui.theme.MarketTheme
import com.marketmonitor.app.ui.theme.ThemeMode

/** In-app settings surface (opened from the top bar). */
@Composable
fun SettingsDialog(
    current: ThemeMode,
    onSelect: (ThemeMode) -> Unit,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("设置", style = MarketTheme.typography.titleMedium) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(MarketTheme.dimensions.spacingSmall)) {
                Text(
                    "外观",
                    style = MarketTheme.typography.labelLarge,
                    color = MarketTheme.colors.info,
                )
                ThemeMode.entries.forEach { mode ->
                    ThemeOption(
                        mode = mode,
                        selected = mode == current,
                        onClick = { onSelect(mode) },
                    )
                }
                HorizontalDivider(color = MarketTheme.colorScheme.outlineVariant)
                Text(
                    "跟随系统：深色/浅色随设备切换；选择立即生效并持久保存。",
                    style = MarketTheme.typography.bodySmall,
                    color = MarketTheme.colorScheme.onSurfaceVariant,
                )
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) {
                Text("完成", color = MarketTheme.colorScheme.primary)
            }
        },
    )
}

@Composable
private fun ThemeOption(
    mode: ThemeMode,
    selected: Boolean,
    onClick: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(vertical = MarketTheme.dimensions.spacingTiny),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(
            selected = selected,
            onClick = onClick,
        )
        Text(
            text = when (mode) {
                ThemeMode.SYSTEM -> "跟随系统"
                ThemeMode.LIGHT -> "浅色"
                ThemeMode.DARK -> "深色"
            },
            style = MaterialTheme.typography.bodyMedium,
        )
    }
}
