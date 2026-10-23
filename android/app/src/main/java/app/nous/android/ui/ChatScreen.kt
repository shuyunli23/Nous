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
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.union
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.nous.android.data.ChatLine
import app.nous.android.data.ModeItem

private val suggestions = listOf(
    "查一下北京今天的天气，并给出行建议",
    "搜索 LangGraph 最近的重要更新，总结三点",
    "解释一下这个项目的 Skill 沉淀机制",
)

@Composable
fun ChatScreen(
    title: String,
    lines: List<ChatLine>,
    loading: Boolean,
    draft: String,
    sending: Boolean,
    statusLine: String?,
    error: String?,
    modes: List<ModeItem>,
    selectedModeId: String?,
    freshChat: Boolean,
    onBack: () -> Unit,
    onDraft: (String) -> Unit,
    onSend: () -> Unit,
    onSelectMode: (String) -> Unit,
) {
    val listState = rememberLazyListState()
    val tail = lines.lastOrNull()
    LaunchedEffect(lines.size, tail?.content?.length, tail?.pending) {
        val last = lines.lastIndex
        if (last >= 0) listState.animateScrollToItem(last)
    }
    val canSend = draft.isNotBlank() && !sending && !loading
    Column(Modifier.fillMaxSize().background(Bg)) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color.White)
                .statusBarsPadding()
                .padding(end = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onBack) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回", tint = Ink)
            }
            Column(Modifier.weight(1f)) {
                Text(title, color = Ink, fontSize = 16.sp, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text("Nous", color = Faint, fontSize = 12.sp)
            }
        }
        Box(Modifier.weight(1f).fillMaxWidth()) {
            when {
                loading && lines.isEmpty() -> LoadingCenter()
                lines.isEmpty() -> ChatHero(onSuggest = onDraft)
                else -> LazyColumn(
                    state = listState,
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp),
                ) {
                    items(lines, key = { it.id }) { line ->
                        MessageRow(line, statusLine)
                    }
                }
            }
        }
        if (!error.isNullOrBlank()) Notice(error, danger = true)
        if (freshChat && modes.isNotEmpty()) {
            ModeRow(modes, selectedModeId, onSelectMode)
        }
        Composer(draft, sending, canSend, onDraft, onSend)
    }
}

@Composable
private fun ChatHero(onSuggest: (String) -> Unit) {
    Column(
        Modifier.fillMaxSize().padding(horizontal = 24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("NOUS WORKBENCH", color = AccentDim, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, letterSpacing = 1.sp)
        Text("能办事的 Agent，", modifier = Modifier.padding(top = 10.dp), color = Ink, fontSize = 28.sp, fontWeight = FontWeight.SemiBold, lineHeight = 34.sp)
        Text("也会记住怎么办。", color = Ink, fontSize = 28.sp, fontWeight = FontWeight.SemiBold, lineHeight = 34.sp)
        Text(
            "搜索、整理、调用 Skill。这条会话会同时出现在网页工作台。",
            modifier = Modifier.padding(top = 10.dp),
            color = Dim,
            fontSize = 14.sp,
            lineHeight = 21.sp,
        )
        Column(Modifier.padding(top = 18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            suggestions.forEach { text ->
                Text(
                    text,
                    modifier = Modifier
                        .clip(RoundedCornerShape(999.dp))
                        .background(Color.White)
                        .border(1.dp, Border, RoundedCornerShape(999.dp))
                        .clickable { onSuggest(text) }
                        .padding(horizontal = 14.dp, vertical = 8.dp),
                    color = TextColor,
                    fontSize = 13.sp,
                )
            }
        }
    }
}

@Composable
private fun ModeRow(modes: List<ModeItem>, selectedModeId: String?, onSelectMode: (String) -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState())
            .padding(horizontal = 16.dp, vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        modes.forEach { mode ->
            val selected = mode.id == selectedModeId
            Text(
                mode.name,
                modifier = Modifier
                    .clip(RoundedCornerShape(999.dp))
                    .background(if (selected) AccentSoft else Color.White)
                    .border(1.dp, if (selected) Accent else Border, RoundedCornerShape(999.dp))
                    .clickable { onSelectMode(mode.id) }
                    .padding(horizontal = 12.dp, vertical = 6.dp),
                color = if (selected) AccentDim else Dim,
                fontSize = 13.sp,
                fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Medium,
            )
        }
    }
}

@Composable
private fun MessageRow(line: ChatLine, statusLine: String?) {
    val mine = line.role == "user"
    if (mine) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
            SelectionContainer {
                Text(
                    line.content,
                    modifier = Modifier
                        .widthIn(max = 300.dp)
                        .shadow(2.dp, RoundedCornerShape(18.dp), ambientColor = Color(0x10102033), spotColor = Color(0x14102033))
                        .clip(RoundedCornerShape(18.dp, 18.dp, 8.dp, 18.dp))
                        .background(Color.White)
                        .border(1.dp, Border, RoundedCornerShape(18.dp, 18.dp, 8.dp, 18.dp))
                        .padding(horizontal = 14.dp, vertical = 11.dp),
                    color = TextColor,
                    fontSize = 15.sp,
                    lineHeight = 23.sp,
                )
            }
        }
        return
    }
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        NousMark(compact = true)
        Column(Modifier.weight(1f)) {
            if (line.pending && line.content.isEmpty()) {
                Text(statusLine ?: "正在思考", color = Dim, fontSize = 14.sp)
            } else if (line.content.isNotEmpty()) {
                SelectionContainer { MarkdownBody(line.content) }
            }
            if (line.pending && line.content.isNotEmpty() && !statusLine.isNullOrBlank()) {
                Text(statusLine, modifier = Modifier.padding(top = 6.dp), color = AccentDim, fontSize = 12.sp)
            }
            if (line.skills.isNotEmpty()) {
                Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    line.skills.forEach { skill -> Pill(skill) }
                }
            }
            if (!line.pending && line.content.isNotEmpty()) {
                val clipboard = LocalClipboardManager.current
                Text(
                    "复制",
                    modifier = Modifier
                        .padding(top = 6.dp)
                        .clickable { clipboard.setText(AnnotatedString(line.content)) },
                    color = Faint,
                    fontSize = 12.sp,
                )
            }
        }
    }
}

@Composable
private fun Composer(
    draft: String,
    sending: Boolean,
    canSend: Boolean,
    onDraft: (String) -> Unit,
    onSend: () -> Unit,
) {
    val shape = RoundedCornerShape(22.dp)
    Row(
        modifier = Modifier
            .windowInsetsPadding(WindowInsets.ime.union(WindowInsets.navigationBars))
            .padding(horizontal = 12.dp, vertical = 10.dp)
            .fillMaxWidth()
            .shadow(8.dp, shape, ambientColor = Color(0x14102033), spotColor = Color(0x1A102033))
            .clip(shape)
            .background(Color.White)
            .border(1.dp, Border, shape)
            .padding(start = 16.dp, end = 6.dp, top = 4.dp, bottom = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.weight(1f).padding(vertical = 10.dp)) {
            if (draft.isEmpty()) Text("发一条消息", color = Faint, fontSize = 16.sp)
            BasicTextField(
                value = draft,
                onValueChange = onDraft,
                modifier = Modifier.fillMaxWidth(),
                textStyle = TextStyle(color = TextColor, fontSize = 16.sp, lineHeight = 22.sp),
                cursorBrush = SolidColor(Accent),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                keyboardActions = KeyboardActions(onSend = { if (canSend) onSend() }),
                maxLines = 5,
            )
        }
        Box(
            modifier = Modifier
                .padding(4.dp)
                .size(40.dp)
                .clip(CircleShape)
                .background(if (canSend || sending) Accent else Color(0xFFE6EBEF))
                .clickable(enabled = canSend, onClick = onSend),
            contentAlignment = Alignment.Center,
        ) {
            if (sending) {
                CircularProgressIndicator(modifier = Modifier.size(16.dp), color = Color.White, strokeWidth = 2.dp)
            } else {
                Icon(
                    Icons.AutoMirrored.Filled.Send,
                    contentDescription = "发送",
                    tint = if (canSend) Color.White else Faint,
                    modifier = Modifier.size(18.dp),
                )
            }
        }
    }
}
