package com.marketmonitor.app.ui.app

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.marketmonitor.app.R
import com.marketmonitor.app.ui.theme.MarketTheme

/**
 * Dense financial-terminal scaffold: a compact top bar (title + settings) and
 * a real icon+label bottom navigation. Screens do not draw their own bars.
 */
@Composable
fun AppScaffold(
    section: AppSection,
    onSectionChange: (AppSection) -> Unit,
    onOpenSettings: () -> Unit,
    content: @Composable () -> Unit,
) {
    Scaffold(
        containerColor = MarketTheme.colorScheme.background,
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .statusBarsPadding()
                    .height(MarketTheme.dimensions.topBarHeight)
                    .padding(horizontal = MarketTheme.dimensions.spacingMedium),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = section.label,
                    style = MarketTheme.typography.titleMedium,
                    modifier = Modifier.weight(1f),
                )
                IconButton(onClick = onOpenSettings) {
                    Icon(
                        imageVector = Icons.Outlined.Settings,
                        contentDescription = stringResource(R.string.settings),
                    )
                }
            }
            HorizontalDivider(color = MarketTheme.colorScheme.outlineVariant)
        },
        bottomBar = {
            NavigationBar(
                modifier = Modifier.height(MarketTheme.dimensions.navigationBarHeight),
                containerColor = MarketTheme.colorScheme.surface,
                tonalElevation = 0.dp,
            ) {
                AppSection.entries.forEach { item ->
                    NavigationBarItem(
                        selected = item == section,
                        onClick = { onSectionChange(item) },
                        icon = {
                            Icon(
                                imageVector = item.icon,
                                contentDescription = item.label,
                            )
                        },
                        label = { Text(item.label, style = MarketTheme.typography.labelSmall) },
                    )
                }
            }
        },
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
        ) {
            content()
        }
    }
}
