package app.nous.android.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.nous.android.data.AskResult
import app.nous.android.data.GraphGlance
import app.nous.android.data.NoteDetailItem
import app.nous.android.data.NoteItem

@Composable
fun NexusScreen(
    panel: Panel,
    notes: List<NoteItem>,
    hits: List<NoteItem>,
    query: String,
    loading: Boolean,
    searching: Boolean,
    error: String?,
    askDraft: String,
    asking: Boolean,
    askResult: AskResult?,
    graph: GraphGlance?,
    graphLoading: Boolean,
    onPanel: (Panel) -> Unit,
    onQuery: (String) -> Unit,
    onSubmit: () -> Unit,
    onOpen: (String) -> Unit,
    onAskDraft: (String) -> Unit,
    onAsk: () -> Unit,
) {
    Column(Modifier.fillMaxSize()) {
        NexusTabs(panel, onPanel)
        if (!error.isNullOrBlank() && panel != Panel.Note) Notice(error, danger = true)
        Box(Modifier.weight(1f).fillMaxWidth()) {
            when (panel) {
            Panel.Search -> NoteList(
                items = hits,
                loading = searching,
                query = query,
                onQuery = onQuery,
                onSubmit = onSubmit,
                onOpen = onOpen,
                placeholder = "在知识库里检索",
                emptyTitle = "还没有检索结果",
                emptyLead = "输入一个词，例如项目名或概念。",
            )
            Panel.Ask -> AskPane(askDraft, asking, askResult, onAskDraft, onAsk)
            Panel.Graph -> GraphPane(graph, graphLoading)
            else -> NoteList(
                items = notes,
                loading = loading,
                query = query,
                onQuery = onQuery,
                onSubmit = onSubmit,
                onOpen = onOpen,
                placeholder = "按标题或摘要筛选",
                emptyTitle = "知识库是空的",
                emptyLead = "在网页的 NexusMind 里写过的笔记会出现在这里。",
            )
            }
        }
    }
}

@Composable
private fun NexusTabs(panel: Panel, onPanel: (Panel) -> Unit) {
    val tabs = listOf(
        Panel.Browse to "笔记",
        Panel.Search to "检索",
        Panel.Ask to "问答",
        Panel.Graph to "图谱",
    )
    Row(
        Modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        tabs.forEach { (target, label) ->
            val selected = panel == target || (panel == Panel.Note && target == Panel.Browse)
            Text(
                label,
                modifier = Modifier
                    .clip(RoundedCornerShape(999.dp))
                    .background(if (selected) Accent else Color.White)
                    .border(1.dp, if (selected) Accent else Border, RoundedCornerShape(999.dp))
                    .clickable { onPanel(target) }
                    .padding(horizontal = 14.dp, vertical = 7.dp),
                color = if (selected) Color.White else TextColor,
                fontSize = 13.sp,
                fontWeight = FontWeight.SemiBold,
            )
        }
    }
}

@Composable
private fun NoteList(
    items: List<NoteItem>,
    loading: Boolean,
    query: String,
    onQuery: (String) -> Unit,
    onSubmit: () -> Unit,
    onOpen: (String) -> Unit,
    placeholder: String,
    emptyTitle: String,
    emptyLead: String,
) {
    Column(Modifier.fillMaxSize()) {
        Box(Modifier.padding(horizontal = 16.dp, vertical = 4.dp)) {
            QueryField(
                value = query,
                onValue = onQuery,
                onSubmit = onSubmit,
                placeholder = placeholder,
            )
        }
        when {
            loading && items.isEmpty() -> Box(Modifier.weight(1f)) { LoadingCenter() }
            items.isEmpty() -> Box(Modifier.weight(1f)) { EmptyCopy(emptyTitle, emptyLead) }
            else -> LazyColumn(
                modifier = Modifier.weight(1f),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                items(items, key = { it.id }) { note ->
                    SurfaceCard(onClick = { onOpen(note.id) }) {
                        if (!note.category.isNullOrBlank()) Pill(note.category)
                        Text(
                            note.title,
                            modifier = Modifier.padding(top = 6.dp),
                            color = Ink,
                            fontSize = 16.sp,
                            fontWeight = FontWeight.SemiBold,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                        if (note.summary.isNotBlank()) {
                            Text(
                                note.summary,
                                modifier = Modifier.padding(top = 4.dp),
                                color = Dim,
                                fontSize = 13.sp,
                                lineHeight = 19.sp,
                                maxLines = 3,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun AskPane(
    draft: String,
    asking: Boolean,
    result: AskResult?,
    onDraft: (String) -> Unit,
    onAsk: () -> Unit,
) {
    Column(Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
        Text("对着知识库提问", color = Ink, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
        Text("回答会带上引用到的笔记。", color = Dim, fontSize = 13.sp, modifier = Modifier.padding(top = 2.dp, bottom = 10.dp))
        QueryField(draft, onDraft, onAsk, if (asking) "正在查找笔记…" else "例如：这个项目怎么部署？")
        when {
            asking && result == null -> Box(Modifier.weight(1f)) { LoadingCenter() }
            result == null -> Box(Modifier.weight(1f)) {
                EmptyCopy("还没有提问", "问题会在已有笔记里找依据，不会凭空编。")
            }
            else -> Column(
                Modifier
                    .weight(1f)
                    .verticalScroll(rememberScrollState())
                    .padding(vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                if (asking) {
                    Text("正在查找笔记…", color = Dim, fontSize = 13.sp)
                }
                MarkdownBody(result.answer.ifBlank { "没有找到可引用的内容。" })
                if (result.citations.isNotEmpty()) {
                    Text("引用", color = Faint, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                    result.citations.forEach { title -> Pill(title) }
                }
            }
        }
    }
}

@Composable
private fun GraphPane(graph: GraphGlance?, loading: Boolean) {
    when {
        loading && graph == null -> LoadingCenter()
        graph == null -> EmptyCopy("图谱还没展开", "笔记之间的关键词和分类会列在这里。")
        else -> Column(
            Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 4.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Stat("笔记", graph.knowledge)
                Stat("关键词", graph.keywords)
                Stat("分类", graph.categories)
            }
            graph.labels.forEach { label ->
                SurfaceCard {
                    Text(label, color = TextColor, fontSize = 14.sp)
                }
            }
        }
    }
}

@Composable
private fun RowScope.Stat(label: String, value: Int) {
    Column(
        Modifier
            .weight(1f)
            .clip(RoundedCornerShape(16.dp))
            .background(Color.White)
            .border(1.dp, Border, RoundedCornerShape(16.dp))
            .padding(horizontal = 12.dp, vertical = 12.dp),
    ) {
        Text(value.toString(), color = Ink, fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
        Text(label, color = Dim, fontSize = 12.sp)
    }
}

@Composable
fun NoteReader(detail: NoteDetailItem?, loading: Boolean, error: String?) {
    when {
        loading && detail == null -> LoadingCenter()
        !error.isNullOrBlank() && detail == null -> Notice(error, danger = true)
        detail == null -> EmptyCopy("没有这篇笔记", "返回列表再打开一次。")
        else -> Column(
            Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (!detail.category.isNullOrBlank()) Pill(detail.category)
            Text(detail.title, color = Ink, fontSize = 24.sp, fontWeight = FontWeight.SemiBold, lineHeight = 30.sp)
            if (detail.summary.isNotBlank()) {
                Text(detail.summary, color = Dim, fontSize = 14.sp, lineHeight = 21.sp)
            }
            if (detail.markdown.isNotBlank()) MarkdownBody(detail.markdown)
        }
    }
}
