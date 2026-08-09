package com.marketmonitor.app.graph

import android.webkit.WebView
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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
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
    industryMapFile: File?,
    industryAtlasFile: File?,
) {
    var viewMode by remember(industryAtlasFile, industryMapFile) {
        mutableStateOf(
            when {
                industryAtlasFile != null -> "atlas"
                industryMapFile != null -> "map"
                else -> "search"
            }
        )
    }
    Column(
        modifier = Modifier.fillMaxSize().padding(vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text("产业链图谱", style = MaterialTheme.typography.titleLarge)
            Button(onClick = onImport) { Text("导入图谱快照") }
        }
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (industryAtlasFile != null) {
                TextButton(onClick = { viewMode = "atlas" }) { Text("产业链全景图") }
            }
            if (industryMapFile != null) {
                TextButton(onClick = { viewMode = "map" }) { Text("SVG 图谱") }
            }
            TextButton(onClick = { viewMode = "search" }) { Text("搜索/详情") }
        }
        if (viewMode == "atlas" && industryAtlasFile != null) {
            IndustryMapView(industryAtlasFile)
        } else if (viewMode == "map" && industryMapFile != null) {
            IndustryMapView(industryMapFile)
        } else {
            OutlinedTextField(
                value = state.query,
                onValueChange = onQueryChange,
                modifier = Modifier.fillMaxWidth(),
                label = { Text("搜索公司、产品或行业") },
                singleLine = true,
            )
            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
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
private fun IndustryMapView(file: File) {
    AndroidView(
        modifier = Modifier.fillMaxSize(),
        factory = { context ->
            WebView(context).apply {
                settings.javaScriptEnabled = true
                settings.domStorageEnabled = true
                settings.allowFileAccess = true
                settings.blockNetworkLoads = true
            }
        },
        update = { webView ->
            val url = "file://" + file.absolutePath
            if (webView.url != url) {
                webView.loadUrl(url)
            }
        },
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
        Text("尚未导入图谱数据。请先导入桌面端生成的图谱快照。")
        return
    }
    if (query.isBlank()) {
        Text("输入关键词开始搜索。")
        return
    }
    if (results.isEmpty()) {
        Text("没有匹配的实体。")
        return
    }
    LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        items(results, key = GraphEntity::entityId) { entity ->
            EntitySearchRow(entity = entity, onClick = { onSelectEntity(entity.entityId) })
        }
    }
}

@Composable
private fun EntitySearchRow(entity: GraphEntity, onClick: () -> Unit) {
    OutlinedCard(modifier = Modifier.fillMaxWidth().clickable(onClick = onClick)) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(entity.name, style = MaterialTheme.typography.titleMedium)
            Text("${entityTypeLabel(entity.entityType)} · ${entity.normalizedName}")
        }
    }
}

@Composable
private fun EntityDetailCard(
    entity: GraphEntity,
    relationships: List<GraphRelationship>,
    repository: GraphRepository,
    onSelectRelationship: (String) -> Unit,
    onBack: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        TextButton(onClick = onBack) { Text("← 返回搜索结果") }
        OutlinedCard(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(12.dp)) {
                Text(entity.name, style = MaterialTheme.typography.titleMedium)
                Text("${entityTypeLabel(entity.entityType)} · ${entity.normalizedName}")
                if (entity.aliases.isNotEmpty()) {
                    Text("别名：${entity.aliases.joinToString("、")}")
                }
            }
        }
        Text("关系（${relationships.size}）", style = MaterialTheme.typography.titleMedium)
        if (relationships.isEmpty()) {
            Text("暂无已确认或待确认的关系。")
        }
        relationships.forEach { relationship ->
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
    OutlinedCard(modifier = Modifier.fillMaxWidth().clickable(onClick = onClick)) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(
                "${source?.name ?: relationship.sourceEntityId} ${relationshipTypeLabel(relationship.relationshipType)} ${target?.name ?: relationship.targetEntityId}",
                style = MaterialTheme.typography.bodyLarge,
            )
            Text(
                "置信度 ${"%.0f".format(relationship.confidence * 100)}% · ${confirmationLabel(relationship.confirmationStatus)} · v${relationship.version}",
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

@Composable
private fun RelationshipDetailCard(detail: GraphRelationshipDetail, onBack: () -> Unit) {
    val relationship = detail.relationship
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        TextButton(onClick = onBack) { Text("← 返回实体") }
        OutlinedCard(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(12.dp)) {
                Text(
                    "${detail.source.name} ${relationshipTypeLabel(relationship.relationshipType)} ${detail.target.name}",
                    style = MaterialTheme.typography.titleMedium,
                )
                Text("确认状态：${confirmationLabel(relationship.confirmationStatus)}")
                Text("置信度：${"%.0f".format(relationship.confidence * 100)}%")
                Text("方向：${if (relationship.direction == "UNDIRECTED") "无向" else "有向"} · 版本：v${relationship.version}")
            }
        }
        Text("来源证据（${detail.evidence.size}）", style = MaterialTheme.typography.titleMedium)
        if (detail.evidence.isEmpty()) {
            Text("该关系没有可追溯的来源证据。")
        }
        detail.evidence.forEach { evidence ->
            OutlinedCard(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Text("来源：${evidence.sourceId}（${evidence.sourceType}）")
                    Text("定位：${evidence.location.summary()}")
                    Text("解析版本：${evidence.parsedVersion}")
                    Text("提取时间：${evidence.extractedAt}")
                    Text("SHA-256：${evidence.sha256.take(16)}…")
                }
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
