package app.nous.android.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.Typography
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

val Ink = Color(0xFF0C1624)
val TextColor = Color(0xFF1B2838)
val Dim = Color(0xFF5B6A79)
val Faint = Color(0xFF8A96A3)
val Bg = Color(0xFFF3F5F8)
val Accent = Color(0xFF0D9488)
val AccentDim = Color(0xFF0F766E)
val Danger = Color(0xFFD64545)
val Border = Color(0x14102033)
val BorderStrong = Color(0x21102033)
val Sidebar = Color(0xFF0D1A26)
val SidebarText = Color(0xFFD7E2EF)
val SidebarMuted = Color(0xFF9FB0C3)
val AccentSoft = Color(0x1A0D9488)
val PanelBg = Color(0xFFF7F8FA)
val WarningBg = Color(0xFFFFF6E8)
val WarningInk = Color(0xFF8A5A12)
val CodeBg = Color(0xFFF3F5F8)

@Composable
fun NousTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = lightColorScheme(
            primary = Accent,
            onPrimary = Color.White,
            background = Bg,
            surface = Color.White,
            onBackground = TextColor,
            onSurface = TextColor,
            error = Danger,
        ),
        typography = Typography(
            bodyLarge = TextStyle(
                fontFamily = FontFamily.SansSerif,
                fontSize = 16.sp,
                lineHeight = 24.sp,
                color = TextColor,
            ),
        ),
        content = content,
    )
}

@Composable
fun NousMark(compact: Boolean = false) {
    val box = if (compact) 36.dp else 52.dp
    val letter = if (compact) 18.sp else 26.sp
    val radius = if (compact) 12.dp else 16.dp
    Box(
        modifier = Modifier
            .size(box)
            .clip(RoundedCornerShape(radius))
            .background(Accent),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = "N",
            color = Color.White,
            fontSize = letter,
            fontWeight = FontWeight.SemiBold,
        )
    }
}
