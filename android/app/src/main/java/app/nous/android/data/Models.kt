package app.nous.android.data

import java.time.Instant
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException

const val DEFAULT_SERVER = "http://10.0.2.2:8000"

data class ModeItem(
    val id: String,
    val name: String,
    val description: String,
)

data class SkillItem(
    val id: String,
    val name: String,
    val description: String,
    val status: String,
    val keywords: String,
)

data class SkillDetailItem(
    val id: String,
    val name: String,
    val description: String,
    val status: String,
    val instruction: String,
    val keywords: String,
)

data class NoteItem(
    val id: String,
    val title: String,
    val summary: String,
    val category: String?,
)

data class NoteDetailItem(
    val id: String,
    val title: String,
    val summary: String,
    val category: String?,
    val markdown: String,
)

data class AskResult(
    val answer: String,
    val citations: List<String>,
)

data class GraphGlance(
    val knowledge: Int,
    val keywords: Int,
    val categories: Int,
    val labels: List<String>,
)

data class TrackItem(
    val id: String,
    val title: String,
    val artist: String,
    val album: String?,
    val durationSec: Int,
)

data class ServerHealth(
    val llmConfigured: Boolean,
    val model: String,
    val provider: String,
)

data class ConversationItem(
    val id: String,
    val title: String,
    val modeName: String?,
    val messageCount: Int,
    val updatedAt: String,
)

data class ConversationDetail(
    val id: String,
    val title: String,
    val lines: List<ChatLine>,
)

data class ChatLine(
    val id: String,
    val role: String,
    val content: String,
    val seq: Int = 0,
    val skills: List<String> = emptyList(),
    val pending: Boolean = false,
)

sealed interface StreamEvent {
    data class Started(val conversationId: String) : StreamEvent
    data class Status(val title: String) : StreamEvent
    data class Token(val text: String) : StreamEvent
    data object Clear : StreamEvent
    data class Done(
        val conversationId: String,
        val messageId: String,
        val answer: String,
        val title: String?,
        val skills: List<String>,
    ) : StreamEvent
}

fun TrackItem.durationLabel(): String {
    if (durationSec <= 0) return ""
    val minutes = durationSec / 60
    val seconds = durationSec % 60
    return "%d:%02d".format(minutes, seconds)
}

fun ConversationItem.metaLine(): String {
    return listOfNotNull(
        modeName?.takeIf { it.isNotBlank() },
        "$messageCount 条",
        formatWhen(updatedAt).takeIf { it.isNotBlank() },
    ).joinToString(" · ")
}

fun formatWhen(raw: String, now: Long = System.currentTimeMillis()): String {
    val epoch = parseEpoch(raw) ?: return ""
    val delta = now - epoch
    if (delta in 0 until 60_000) return "刚刚"
    if (delta in 0 until 3_600_000) return "${delta / 60_000} 分钟前"
    val zone = ZoneId.systemDefault()
    val time = Instant.ofEpochMilli(epoch).atZone(zone)
    val today = Instant.ofEpochMilli(now).atZone(zone).toLocalDate()
    val clock = time.format(DateTimeFormatter.ofPattern("H:mm"))
    return when (val date = time.toLocalDate()) {
        today -> clock
        today.minusDays(1) -> "昨天 $clock"
        else -> if (date.year == today.year) {
            time.format(DateTimeFormatter.ofPattern("M月d日"))
        } else {
            time.format(DateTimeFormatter.ofPattern("yyyy年M月d日"))
        }
    }
}

private fun parseEpoch(raw: String): Long? {
    if (raw.isBlank()) return null
    try {
        return Instant.parse(raw).toEpochMilli()
    } catch (_: DateTimeParseException) {
    }
    try {
        return OffsetDateTime.parse(raw).toInstant().toEpochMilli()
    } catch (_: DateTimeParseException) {
    }
    return try {
        LocalDateTime.parse(raw).atZone(ZoneId.systemDefault()).toInstant().toEpochMilli()
    } catch (_: DateTimeParseException) {
        null
    }
}
