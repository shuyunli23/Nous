package app.nous.android.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.nous.android.data.ServerHealth
import app.nous.android.data.TrackItem

@Composable
fun HomeShell(
    section: Section,
    panel: Panel,
    health: ServerHealth?,
    nowPlaying: TrackItem?,
    playing: Boolean,
    onSection: (Section) -> Unit,
    onBack: () -> Unit,
    onDisconnect: () -> Unit,
    onToggle: () -> Unit,
    content: @Composable () -> Unit,
) {
    val reading = panel == Panel.Skill || panel == Panel.Note
    Column(Modifier.fillMaxSize().background(Bg)) {
        if (reading) {
            SubHeader(
                title = if (panel == Panel.Skill) "Skill" else "笔记",
                onBack = onBack,
            )
        } else {
            ShellHeader(section, health, onDisconnect)
        }
        Column(Modifier.weight(1f).fillMaxWidth()) {
            content()
        }
        if (!reading && nowPlaying != null) {
            NowPlaying(nowPlaying, playing, onToggle)
        }
        if (!reading) {
            ProductNav(section, onSection)
        }
    }
}

@Composable
private fun ShellHeader(section: Section, health: ServerHealth?, onDisconnect: () -> Unit) {
    val (name, tag) = when (section) {
        Section.Nous -> "Nous" to "工作台"
        Section.Skills -> "Skill" to "经验与工具"
        Section.Nexus -> "NexusMind" to "知识库"
        Section.Harmony -> "Harmony" to "音乐"
    }
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Sidebar)
            .statusBarsPadding()
            .padding(start = 16.dp, end = 8.dp, top = 10.dp, bottom = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        NousMark(compact = true)
        Column(Modifier.padding(start = 12.dp).weight(1f)) {
            Text(name, color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
            Text(
                headerTag(section, tag, health),
                color = SidebarMuted,
                fontSize = 12.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        Text(
            "断开",
            modifier = Modifier
                .clip(RoundedCornerShape(999.dp))
                .clickable(onClick = onDisconnect)
                .padding(horizontal = 12.dp, vertical = 8.dp),
            color = SidebarText,
            fontSize = 13.sp,
        )
    }
}

@Composable
private fun SubHeader(title: String, onBack: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color.White)
            .statusBarsPadding()
            .padding(end = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        androidx.compose.material3.IconButton(onClick = onBack) {
            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回", tint = Ink)
        }
        Text(title, color = Ink, fontSize = 17.sp, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun NowPlaying(track: TrackItem, playing: Boolean, onToggle: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color.White)
            .padding(horizontal = 16.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(track.title, color = Ink, fontSize = 14.sp, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(track.artist, color = Dim, fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        Box(
            modifier = Modifier
                .size(36.dp)
                .clip(CircleShape)
                .background(Accent)
                .clickable(onClick = onToggle),
            contentAlignment = Alignment.Center,
        ) {
            if (playing) {
                PauseBars(Color.White)
            } else {
                Icon(
                    Icons.Filled.PlayArrow,
                    contentDescription = "播放",
                    tint = Color.White,
                    modifier = Modifier.size(18.dp),
                )
            }
        }
    }
}

@Composable
private fun ProductNav(section: Section, onSection: (Section) -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color.White)
            .navigationBarsPadding()
            .padding(horizontal = 8.dp, vertical = 6.dp),
        horizontalArrangement = Arrangement.SpaceEvenly,
    ) {
        NavItem(Section.Nous, "对话", Icons.Filled.List, section, onSection)
        NavItem(Section.Skills, "Skill", Icons.Filled.Star, section, onSection)
        NavItem(Section.Nexus, "知识", Icons.Filled.Search, section, onSection)
        NavItem(Section.Harmony, "音乐", Icons.Filled.PlayArrow, section, onSection)
    }
}

@Composable
private fun NavItem(
    target: Section,
    label: String,
    icon: ImageVector,
    current: Section,
    onSection: (Section) -> Unit,
) {
    val active = target == current
    Column(
        modifier = Modifier
            .clip(RoundedCornerShape(14.dp))
            .background(if (active) AccentSoft else Color.Transparent)
            .clickable { onSection(target) }
            .padding(horizontal = 14.dp, vertical = 7.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(icon, contentDescription = label, tint = if (active) AccentDim else Faint, modifier = Modifier.size(20.dp))
        Spacer(Modifier.size(2.dp))
        Text(
            label,
            color = if (active) AccentDim else Dim,
            fontSize = 11.sp,
            fontWeight = if (active) FontWeight.SemiBold else FontWeight.Medium,
        )
    }
}

private fun headerTag(section: Section, fallback: String, health: ServerHealth?): String {
    if (section != Section.Nous || health == null) return fallback
    if (!health.llmConfigured) return "已连接，模型还没配置"
    val model = health.model.ifBlank { health.provider }
    return if (model.isBlank()) fallback else model
}
