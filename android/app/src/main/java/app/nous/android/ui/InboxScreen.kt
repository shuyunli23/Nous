package app.nous.android.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.nous.android.data.ConversationItem
import app.nous.android.data.ServerHealth
import app.nous.android.data.metaLine

@Composable
fun InboxScreen(
    health: ServerHealth?,
    conversations: List<ConversationItem>,
    loading: Boolean,
    error: String?,
    embedded: Boolean = false,
    onRefresh: () -> Unit,
    onDisconnect: () -> Unit,
    onOpen: (String) -> Unit,
    onDelete: (String) -> Unit,
    onNew: () -> Unit,
) {
    var pendingDelete by remember { mutableStateOf<String?>(null) }
    val deleting = conversations.find { it.id == pendingDelete }
    Box(modifier = Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize()) {
            if (!embedded) {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(start = 20.dp, end = 8.dp, top = 12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text("Nous", modifier = Modifier.weight(1f), color = Ink, fontSize = 28.sp, fontWeight = FontWeight.SemiBold)
                    TextButton(onClick = onDisconnect) { Text("断开", color = Dim) }
                }
            }
            Row(
                modifier = Modifier.fillMaxWidth().padding(start = 16.dp, end = 4.dp, top = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text("会话", color = Ink, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                    Text("和网页工作台是同一份", color = Faint, fontSize = 12.sp)
                }
                if (loading && conversations.isNotEmpty()) {
                    CircularProgressIndicator(
                        modifier = Modifier.padding(end = 12.dp).size(16.dp),
                        color = Accent,
                        strokeWidth = 2.dp,
                    )
                } else {
                    IconButton(onClick = onRefresh) {
                        Icon(Icons.Filled.Refresh, contentDescription = "刷新", tint = Ink)
                    }
                }
            }
            if (health != null && !health.llmConfigured) {
                Notice("模型还没配置。在网页的设置里填好密钥后，这里就能直接对话。")
            }
            if (!error.isNullOrBlank()) Notice(error, danger = true)
            when {
                loading && conversations.isEmpty() -> Box(Modifier.weight(1f)) { LoadingCenter() }
                conversations.isEmpty() -> Box(Modifier.weight(1f)) {
                    EmptyCopy(
                        "还没有会话",
                        "从这里发出的消息，会和网页工作台是同一份。",
                    )
                }
                else -> LazyColumn(
                    modifier = Modifier.weight(1f),
                    contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 96.dp),
                    verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(10.dp),
                ) {
                    items(conversations, key = { it.id }) { item ->
                        ConversationCard(item, onOpen = { onOpen(item.id) }, onDelete = { pendingDelete = item.id })
                    }
                }
            }
        }
        FloatingActionButton(
            onClick = onNew,
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .then(if (embedded) Modifier else Modifier.navigationBarsPadding())
                .padding(16.dp),
            containerColor = Accent,
            contentColor = Color.White,
            shape = CircleShape,
        ) {
            Icon(Icons.Filled.Add, contentDescription = "新对话")
        }
    }
    if (deleting != null) {
        AlertDialog(
            onDismissRequest = { pendingDelete = null },
            title = { Text("删除会话") },
            text = { Text("「${deleting.title}」会从网页工作台里一起消失。") },
            confirmButton = {
                TextButton(onClick = {
                    onDelete(deleting.id)
                    pendingDelete = null
                }) { Text("删除", color = Danger) }
            },
            dismissButton = {
                TextButton(onClick = { pendingDelete = null }) { Text("取消") }
            },
        )
    }
}

@Composable
private fun ConversationCard(
    item: ConversationItem,
    onOpen: () -> Unit,
    onDelete: () -> Unit,
) {
    SurfaceCard(onClick = onOpen) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(
                    item.title,
                    color = Ink,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    item.metaLine(),
                    modifier = Modifier.padding(top = 4.dp),
                    color = Dim,
                    fontSize = 13.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            IconButton(onClick = onDelete) {
                Icon(Icons.Filled.Delete, contentDescription = "删除", tint = Faint)
            }
        }
    }
}
