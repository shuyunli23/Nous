package app.nous.android.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.nous.android.data.SkillDetailItem
import app.nous.android.data.SkillItem

@Composable
fun SkillsScreen(
    skills: List<SkillItem>,
    query: String,
    loading: Boolean,
    error: String?,
    onQuery: (String) -> Unit,
    onSearch: () -> Unit,
    onOpen: (String) -> Unit,
) {
    Column(Modifier.fillMaxSize()) {
        Column(Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
            Text("已沉淀的 Skill", color = Ink, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
            Text(
                "对话时会按这些经验来办事。",
                modifier = Modifier.padding(top = 2.dp, bottom = 10.dp),
                color = Dim,
                fontSize = 13.sp,
            )
            QueryField(query, onQuery, onSearch, "按名称或描述找")
        }
        if (!error.isNullOrBlank()) Notice(error, danger = true)
            when {
                loading && skills.isEmpty() -> Box(Modifier.weight(1f)) { LoadingCenter() }
                skills.isEmpty() -> Box(Modifier.weight(1f)) {
                    EmptyCopy("还没有 Skill", "在网页工作台里沉淀一条经验后，这里会列出来。")
                }
                else -> LazyColumn(
                    modifier = Modifier.weight(1f),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                items(skills, key = { it.id }) { skill ->
                    SurfaceCard(onClick = { onOpen(skill.id) }) {
                        Text(skill.name, color = Ink, fontSize = 16.sp, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        if (skill.status.isNotBlank()) {
                            Pill(skillStatusLabel(skill.status))
                        }
                        if (skill.description.isNotBlank()) {
                            Text(
                                skill.description,
                                modifier = Modifier.padding(top = 6.dp),
                                color = Dim,
                                fontSize = 13.sp,
                                lineHeight = 19.sp,
                                maxLines = 3,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                        if (skill.keywords.isNotBlank()) {
                            Text(skill.keywords, modifier = Modifier.padding(top = 6.dp), color = Faint, fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun SkillDetailScreen(detail: SkillDetailItem?, loading: Boolean, error: String?) {
    when {
        loading && detail == null -> LoadingCenter()
        !error.isNullOrBlank() && detail == null -> Notice(error, danger = true)
        detail == null -> EmptyCopy("没有这条 Skill", "返回列表再打开一次。")
        else -> Column(
            Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(detail.name, color = Ink, fontSize = 24.sp, fontWeight = FontWeight.SemiBold, lineHeight = 30.sp)
            if (detail.status.isNotBlank()) Pill(skillStatusLabel(detail.status))
            if (detail.description.isNotBlank()) {
                Text(detail.description, color = Dim, fontSize = 15.sp, lineHeight = 22.sp)
            }
            if (detail.keywords.isNotBlank()) {
                Text("触发词", color = Faint, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                Text(detail.keywords, color = TextColor, fontSize = 14.sp, lineHeight = 20.sp)
            }
            if (detail.instruction.isNotBlank()) {
                Text("做法", color = Faint, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                MarkdownBody(detail.instruction)
            }
        }
    }
}
