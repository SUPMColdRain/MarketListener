package com.marketmonitor.app.graph

import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.marketmonitor.app.ui.theme.MarketTheme
import com.marketmonitor.app.ui.theme.MarketType
import java.io.File

/** Industry-graph tab: search, entity detail, relationships and source trace. */
@Composable
fun GraphTab(
    repository: GraphRepository?,
    state: GraphSearchState,
    onQueryChange: (String) -> Unit,
    onSelectEntity: (String) -> Unit,
    onSelectRelationship: (String) -> Unit,
    onImport: () -> Unit,
    industryAtlasFile: File?,
) {
    var viewMode by remember(industryAtlasFile) { mutableStateOf(if (industryAtlasFile != null) "atlas" else "search") }
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = MarketTheme.dimensions.spacingMedium)
            .padding(vertical = MarketTheme.dimensions.spacingSmall),
        verticalArrangement = Arrangement.spacedBy(MarketTheme.dimensions.spacingSmall),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                if (industryAtlasFile != null) {
                    TextButton(onClick = { viewMode = "atlas" }) {
                        Text(
                            text = "产业链全景图",
                            style = MarketTheme.typography.labelLarge,
                            color = if (viewMode == "atlas") MarketTheme.colors.info else MarketTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                TextButton(onClick = { viewMode = "search" }) {
                    Text(
                        text = "搜索/详情",
                        style = MarketTheme.typography.labelLarge,
                        color = if (viewMode == "search") MarketTheme.colors.info else MarketTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Button(onClick = onImport) { Text("导入快照") }
        }
        HorizontalDivider(color = MarketTheme.colorScheme.outlineVariant)
        if (viewMode == "atlas" && industryAtlasFile != null) {
            IndustryMapView(industryAtlasFile, isDark = MarketTheme.isDark)
        } else {
            OutlinedTextField(
                value = state.query,
                onValueChange = onQueryChange,
                modifier = Modifier.fillMaxWidth(),
                label = { Text("搜索公司、产品或行业") },
                singleLine = true,
            )
            state.error?.let { Text(it, style = MarketTheme.typography.bodySmall, color = MarketTheme.colors.error) }
            when {
                state.selectedRelationshipId != null -> {
                    repository?.relationshipDetail(state.selectedRelationshipId)?.let { detail ->
                        RelationshipDetailCard(detail, onBack = { onSelectEntity(state.selectedEntityId ?: detail.source.entityId) })
                    }
                }
                state.selectedEntityId != null -> {
                    repository?.entityFor(state.selectedEntityId)?.let { entity ->
                        EntityDetailCard(
                            entity = entity,
                            relationships = repository.relationshipsFor(entity.entityId),
                            repository = repository,
                            onSelectRelationship = onSelectRelationship,
                            onBack = { onQueryChange(state.query) },
                        )
                    }
                }
                else -> SearchResults(
                    query = state.query,
                    results = state.results,
                    snapshotLoaded = state.snapshotLoaded,
                    onSelectEntity = onSelectEntity,
                )
            }
        }
    }
}

@Composable
private fun IndustryMapView(file: File, isDark: Boolean) {
    AndroidView(
        modifier = Modifier.fillMaxSize(),
        factory = { context ->
            WebView(context).apply {
                settings.javaScriptEnabled = true
                settings.domStorageEnabled = true
                settings.allowFileAccess = true
                settings.blockNetworkLoads = true
                webViewClient = object : WebViewClient() {
                    override fun onPageFinished(view: WebView?, url: String?) {
                        injectAtlasTheme(view, isDark)
                    }
                }
            }
        },
        update = { webView ->
            val url = "file://" + file.absolutePath
            if (webView.url != url) {
                webView.loadUrl(url)
            } else {
                injectAtlasTheme(webView, isDark)
            }
        },
    )
}

/**
 * Future-proof theme bridge: only calls the page-level API when the bundled
 * industry atlas actually exposes it, so older HTML keeps working untouched.
 */
private fun injectAtlasTheme(webView: WebView?, isDark: Boolean) {
    if (webView == null) return
    val mode = if (isDark) "'dark'" else "'light'"
    webView.evaluateJavascript(
        "if (typeof window.setMarketListenerTheme === 'function') { window.setMarketListenerTheme($mode); }",
        null,
    )
}

@Composable
private fun SearchResults(
    query: String,
    results: List<GraphEntity>,
    snapshotLoaded: Boolean,
    onSelectEntity: (String) -> Unit,
) {
    if (!snapshotLoaded) {
        Text(
            text = "尚未导入图谱数据。请先导入桌面端生成的图谱快照。",
            style = MarketTheme.typography.bodySmall,
            color = MarketTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(vertical = MarketTheme.dimensions.spacingMedium),
        )
        return
    }
    if (query.isBlank()) {
        Text(
            text = "输入关键词开始搜索。",
            style = MarketTheme.typography.bodySmall,
            color = MarketTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(vertical = MarketTheme.dimensions.spacingMedium),
        )
        return
    }
    if (results.isEmpty()) {
        Text(
            text = "没有匹配的实体。",
            style = MarketTheme.typography.bodySmall,
            color = MarketTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(vertical = MarketTheme.dimensions.spacingMedium),
        )
        return
    }
    LazyColumn {
        items(results, key = GraphEntity::entityId) { entity ->
            EntitySearchRow(entity = entity, onClick = { onSelectEntity(entity.entityId) })
        }
    }
}

@Composable
private fun EntitySearchRow(entity: GraphEntity, onClick: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(vertical = MarketTheme.dimensions.spacingSmall),
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        Text(entity.name, style = MarketTheme.typography.titleSmall)
        Text(
            text = "${entityTypeLabel(entity.entityType)} · ${entity.normalizedName}",
            style = MarketTheme.typography.bodySmall,
            color = MarketTheme.colorScheme.onSurfaceVariant,
        )
    }
    HorizontalDivider(color = MarketTheme.colorScheme.outlineVariant)
}

@Composable
private fun EntityDetailCard(
    entity: GraphEntity,
    relationships: List<GraphRelationship>,
    repository: GraphRepository,
    onSelectRelationship: (String) -> Unit,
    onBack: () -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(MarketTheme.dimensions.spacingSmall),
    ) {
        item {
            TextButton(onClick = onBack) { Text("← 返回搜索结果") }
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = MarketTheme.dimensions.spacingSmall),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                Text(entity.name, style = MarketTheme.typography.titleSmall)
                Text(
                    text = "${entityTypeLabel(entity.entityType)} · ${entity.normalizedName}",
                    style = MarketTheme.typography.bodySmall,
                    color = MarketTheme.colorScheme.onSurfaceVariant,
                )
                if (entity.aliases.isNotEmpty()) {
                    Text(
                        text = "别名：${entity.aliases.joinToString("、")}",
                        style = MarketTheme.typography.bodySmall,
                        color = MarketTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
        item {
            HorizontalDivider(color = MarketTheme.colorScheme.outlineVariant)
        }
        item {
            Text("关系（${relationships.size}）", style = MarketTheme.typography.labelLarge, color = MarketTheme.colorScheme.onSurfaceVariant)
        }
        if (relationships.isEmpty()) {
            item {
                Text(
                    text = "暂无已确认或待确认的关系。",
                    style = MarketTheme.typography.bodySmall,
                    color = MarketTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        items(relationships, key = GraphRelationship::relationshipId) { relationship ->
            RelationshipRow(
                relationship = relationship,
                repository = repository,
                onClick = { onSelectRelationship(relationship.relationshipId) },
            )
        }
    }
}

@Composable
private fun RelationshipRow(
    relationship: GraphRelationship,
    repository: GraphRepository,
    onClick: () -> Unit,
) {
    val source = repository.entityFor(relationship.sourceEntityId)
    val target = repository.entityFor(relationship.targetEntityId)
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(vertical = MarketTheme.dimensions.spacingSmall),
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        Text(
            text = "${source?.name ?: relationship.sourceEntityId} ${relationshipTypeLabel(relationship.relationshipType)} ${target?.name ?: relationship.targetEntityId}",
            style = MarketTheme.typography.bodyMedium,
            color = MarketTheme.colorScheme.onSurface,
        )
        Text(
            text = "置信度 ${"%.0f".format(relationship.confidence * 100)}% · ${confirmationLabel(relationship.confirmationStatus)} · v${relationship.version}",
            style = MarketTheme.typography.bodySmall,
            color = MarketTheme.colorScheme.onSurfaceVariant,
        )
        HorizontalDivider(color = MarketTheme.colorScheme.outlineVariant)
    }
}

@Composable
private fun RelationshipDetailCard(detail: GraphRelationshipDetail, onBack: () -> Unit) {
    val relationship = detail.relationship
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(MarketTheme.dimensions.spacingSmall),
    ) {
        item {
            TextButton(onClick = onBack) { Text("← 返回实体") }
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = MarketTheme.dimensions.spacingSmall),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                Text(
                    text = "${detail.source.name} ${relationshipTypeLabel(relationship.relationshipType)} ${detail.target.name}",
                    style = MarketTheme.typography.titleSmall,
                )
                Text(
                    text = "确认状态：${confirmationLabel(relationship.confirmationStatus)}",
                    style = MarketTheme.typography.bodySmall,
                    color = MarketTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    text = "置信度：${"%.0f".format(relationship.confidence * 100)}%",
                    style = MarketTheme.typography.bodySmall,
                    color = MarketTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    text = "方向：${if (relationship.direction == "UNDIRECTED") "无向" else "有向"} · 版本：v${relationship.version}",
                    style = MarketTheme.typography.bodySmall,
                    color = MarketTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        item {
            HorizontalDivider(color = MarketTheme.colorScheme.outlineVariant)
        }
        item {
            Text("来源证据（${detail.evidence.size}）", style = MarketTheme.typography.labelLarge, color = MarketTheme.colorScheme.onSurfaceVariant)
        }
        if (detail.evidence.isEmpty()) {
            item {
                Text(
                    text = "该关系没有可追溯的来源证据。",
                    style = MarketTheme.typography.bodySmall,
                    color = MarketTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        items(detail.evidence, key = { it.sha256 }) { evidence ->
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = MarketTheme.dimensions.spacingSmall),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                Text(
                    text = "来源：${evidence.sourceId}（${evidence.sourceType}）",
                    style = MarketTheme.typography.bodySmall,
                    color = MarketTheme.colorScheme.onSurface,
                )
                Text(
                    text = "定位：${evidence.location.summary()}",
                    style = MarketTheme.typography.bodySmall,
                    color = MarketTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    text = "解析版本：${evidence.parsedVersion}",
                    style = MarketTheme.typography.bodySmall,
                    color = MarketTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    text = "提取时间：${evidence.extractedAt}",
                    style = MarketTheme.typography.bodySmall,
                    color = MarketTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    text = "SHA-256：${evidence.sha256.take(16)}…",
                    style = MarketType.code,
                    color = MarketTheme.colorScheme.onSurfaceVariant,
                )
                HorizontalDivider(color = MarketTheme.colorScheme.outlineVariant)
            }
        }
    }
}

private fun entityTypeLabel(entityType: String): String = when (entityType) {
    "COMPANY" -> "公司"
    "PRODUCT" -> "产品"
    "INDUSTRY" -> "行业"
    "SUPPLIER" -> "供应商"
    "CUSTOMER" -> "客户"
    "RAW_MATERIAL" -> "原材料"
    "SERVICE" -> "服务"
    "REGION" -> "区域"
    else -> entityType
}

private fun relationshipTypeLabel(relationshipType: String): String = when (relationshipType) {
    "SUPPLIES" -> "供应"
    "PURCHASES" -> "采购"
    "PRODUCES" -> "生产"
    "PART_OF" -> "属于"
    "COMPETES_WITH" -> "与…竞争"
    "DISTRIBUTES" -> "分销"
    "USES" -> "使用"
    "OWNS" -> "持有"
    "CUSTOMER_OF" -> "是…客户"
    else -> relationshipType
}

private fun confirmationLabel(status: String): String = when (status) {
    "PENDING" -> "待人工确认"
    "AUTO_ACCEPTED" -> "自动接受"
    "HUMAN_CONFIRMED" -> "人工确认"
    "REJECTED" -> "已否决"
    "SUPERSEDED" -> "已被修订取代"
    else -> status
}
