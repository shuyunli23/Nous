package app.nous.android.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.nous.android.data.TrackItem
import app.nous.android.data.durationLabel

@Composable
fun HarmonyScreen(
    tracks: List<TrackItem>,
    loading: Boolean,
    error: String?,
    playingId: String?,
    playing: Boolean,
    onRefresh: () -> Unit,
    onToggle: (TrackItem) -> Unit,
) {
    Column(Modifier.fillMaxSize()) {
        Row(
            Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text("曲库", color = Ink, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                Text("和电脑上的 Harmony 是同一份。", color = Dim, fontSize = 13.sp)
            }
            Text(
                "刷新",
                modifier = Modifier.clickable(onClick = onRefresh).padding(8.dp),
                color = AccentDim,
                fontSize = 13.sp,
                fontWeight = FontWeight.SemiBold,
            )
        }
        if (!error.isNullOrBlank()) Notice(error, danger = true)
        when {
            loading && tracks.isEmpty() -> Box(Modifier.weight(1f)) { LoadingCenter() }
            tracks.isEmpty() -> Box(Modifier.weight(1f)) {
                EmptyCopy("曲库是空的", "在电脑的 Harmony 里放进音乐后，这里就能播。")
            }
            else -> LazyColumn(
                modifier = Modifier.weight(1f),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(tracks, key = { it.id }) { track ->
                    val active = track.id == playingId
                    SurfaceCard(onClick = { onToggle(track) }) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(
                                modifier = Modifier
                                    .size(40.dp)
                                    .clip(CircleShape)
                                    .background(if (active) Accent else AccentSoft),
                                contentAlignment = Alignment.Center,
                            ) {
                                if (active && playing) {
                                    PauseBars(Color.White, Modifier.size(12.dp))
                                } else {
                                    Icon(
                                        Icons.Filled.PlayArrow,
                                        contentDescription = "播放",
                                        tint = if (active) Color.White else AccentDim,
                                        modifier = Modifier.size(20.dp),
                                    )
                                }
                            }
                            Column(Modifier.padding(start = 12.dp).weight(1f)) {
                                Text(track.title, color = Ink, fontSize = 15.sp, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                val meta = listOfNotNull(track.artist, track.album, track.durationLabel().ifBlank { null })
                                    .joinToString(" · ")
                                Text(meta, color = Dim, fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            }
                        }
                    }
                }
            }
        }
    }
}
