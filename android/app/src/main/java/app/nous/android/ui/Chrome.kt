package app.nous.android.ui

import android.app.Activity
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat

@Composable
fun SystemBars(lightBackground: Boolean) {
    val view = LocalView.current
    if (view.isInEditMode) return
    SideEffect {
        val window = (view.context as Activity).window
        WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = lightBackground
    }
}

@Composable
fun WorkspaceBackdrop(content: @Composable () -> Unit) {
    Box(Modifier.fillMaxSize().background(Bg)) {
        Box(
            Modifier
                .fillMaxWidth()
                .height(240.dp)
                .background(
                    Brush.radialGradient(
                        colors = listOf(Color(0x1F0D9488), Color.Transparent),
                        center = Offset(120f, 0f),
                        radius = 720f,
                    ),
                ),
        )
        content()
    }
}

@Composable
fun SurfaceCard(
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    content: @Composable () -> Unit,
) {
    val shape = RoundedCornerShape(16.dp)
    Column(
        modifier
            .fillMaxWidth()
            .shadow(6.dp, shape, ambientColor = Color(0x14102033), spotColor = Color(0x1F102033))
            .clip(shape)
            .background(Color.White)
            .border(1.dp, Border, shape)
            .then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier)
            .padding(horizontal = 16.dp, vertical = 14.dp),
    ) {
        content()
    }
}

@Composable
fun QueryField(
    value: String,
    onValue: (String) -> Unit,
    onSubmit: () -> Unit,
    placeholder: String,
) {
    val shape = RoundedCornerShape(12.dp)
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(shape)
            .background(Color.White)
            .border(1.dp, BorderStrong, shape)
            .padding(horizontal = 14.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.weight(1f)) {
            if (value.isEmpty()) Text(placeholder, color = Faint, fontSize = 15.sp)
            BasicTextField(
                value = value,
                onValueChange = onValue,
                modifier = Modifier.fillMaxWidth(),
                textStyle = androidx.compose.ui.text.TextStyle(color = TextColor, fontSize = 15.sp),
                cursorBrush = SolidColor(Accent),
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { onSubmit() }),
            )
        }
        Text(
            "检索",
            modifier = Modifier
                .clip(RoundedCornerShape(999.dp))
                .clickable(onClick = onSubmit)
                .padding(horizontal = 8.dp, vertical = 4.dp),
            color = AccentDim,
            fontSize = 13.sp,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

@Composable
fun LoadingCenter() {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        CircularProgressIndicator(color = Accent, strokeWidth = 2.dp, modifier = Modifier.size(22.dp))
    }
}

@Composable
fun EmptyCopy(title: String, lead: String) {
    Column(
        Modifier.fillMaxSize().padding(horizontal = 28.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text(title, color = Ink, fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
        Text(lead, modifier = Modifier.padding(top = 6.dp), color = Dim, fontSize = 14.sp, lineHeight = 21.sp)
    }
}

@Composable
fun Notice(text: String, danger: Boolean = false) {
    Text(
        text,
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 6.dp)
            .clip(RoundedCornerShape(12.dp))
            .background(if (danger) Color(0xFFFFF1F1) else WarningBg)
            .padding(horizontal = 14.dp, vertical = 10.dp),
        color = if (danger) Danger else WarningInk,
        fontSize = 13.sp,
        lineHeight = 18.sp,
    )
}

@Composable
fun Pill(text: String) {
    Text(
        text,
        modifier = Modifier
            .clip(RoundedCornerShape(999.dp))
            .background(AccentSoft)
            .padding(horizontal = 8.dp, vertical = 3.dp),
        color = AccentDim,
        fontSize = 11.sp,
        fontWeight = FontWeight.SemiBold,
    )
}

@Composable
fun PauseBars(tint: Color, modifier: Modifier = Modifier) {
    Row(
        modifier = modifier,
        horizontalArrangement = Arrangement.spacedBy(3.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(width = 3.dp, height = 12.dp).clip(RoundedCornerShape(1.dp)).background(tint))
        Box(Modifier.size(width = 3.dp, height = 12.dp).clip(RoundedCornerShape(1.dp)).background(tint))
    }
}

fun skillStatusLabel(status: String): String = when (status) {
    "active" -> "启用"
    "draft" -> "草稿"
    "disabled" -> "停用"
    "deprecated" -> "弃用"
    else -> status.ifBlank { "Skill" }
}

@Composable
fun MarkdownBody(markdown: String, color: Color = TextColor) {
    val blocks = remember(markdown) { parseMarkdown(markdown) }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        blocks.forEach { block ->
            when (block) {
                is MdBlock.Heading -> Text(
                    inlineMarkdown(block.text),
                    color = Ink,
                    fontSize = if (block.level <= 2) 18.sp else 16.sp,
                    fontWeight = FontWeight.SemiBold,
                    lineHeight = 26.sp,
                )
                is MdBlock.Bullet -> Row {
                    Text("•", color = Accent, modifier = Modifier.padding(end = 8.dp, top = 1.dp))
                    Text(inlineMarkdown(block.text), color = color, fontSize = 15.sp, lineHeight = 23.sp)
                }
                is MdBlock.Quote -> Text(
                    inlineMarkdown(block.text),
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(8.dp))
                        .background(AccentSoft)
                        .padding(horizontal = 12.dp, vertical = 8.dp),
                    color = TextColor,
                    fontSize = 14.sp,
                    lineHeight = 21.sp,
                )
                is MdBlock.Code -> Text(
                    block.text.ifBlank { " " },
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState())
                        .clip(RoundedCornerShape(10.dp))
                        .background(CodeBg)
                        .padding(12.dp),
                    color = Ink,
                    fontSize = 13.sp,
                    lineHeight = 19.sp,
                    fontFamily = FontFamily.Monospace,
                )
                is MdBlock.Paragraph -> Text(
                    inlineMarkdown(block.text),
                    color = color,
                    fontSize = 15.sp,
                    lineHeight = 24.sp,
                )
            }
        }
    }
}

private sealed interface MdBlock {
    data class Heading(val level: Int, val text: String) : MdBlock
    data class Paragraph(val text: String) : MdBlock
    data class Bullet(val text: String) : MdBlock
    data class Quote(val text: String) : MdBlock
    data class Code(val text: String) : MdBlock
}

private fun parseMarkdown(source: String): List<MdBlock> {
    val lines = source.replace("\r\n", "\n").split('\n')
    val blocks = mutableListOf<MdBlock>()
    val paragraph = StringBuilder()
    fun flush() {
        val text = paragraph.toString().trim()
        if (text.isNotEmpty()) blocks += MdBlock.Paragraph(text)
        paragraph.clear()
    }
    var index = 0
    while (index < lines.size) {
        val raw = lines[index]
        if (raw.trimStart().startsWith("```")) {
            flush()
            val code = StringBuilder()
            index += 1
            while (index < lines.size && !lines[index].trimStart().startsWith("```")) {
                if (code.isNotEmpty()) code.append('\n')
                code.append(lines[index])
                index += 1
            }
            blocks += MdBlock.Code(code.toString())
            index += 1
            continue
        }
        val line = raw.trim()
        when {
            line.isEmpty() -> flush()
            line.startsWith("### ") -> {
                flush()
                blocks += MdBlock.Heading(3, line.removePrefix("### "))
            }
            line.startsWith("## ") -> {
                flush()
                blocks += MdBlock.Heading(2, line.removePrefix("## "))
            }
            line.startsWith("# ") -> {
                flush()
                blocks += MdBlock.Heading(1, line.removePrefix("# "))
            }
            line.startsWith("> ") -> {
                flush()
                blocks += MdBlock.Quote(line.removePrefix("> "))
            }
            line.startsWith("- ") || line.startsWith("* ") -> {
                flush()
                blocks += MdBlock.Bullet(line.drop(2))
            }
            line.length > 2 && line[0].isDigit() && line.contains(". ") -> {
                flush()
                blocks += MdBlock.Bullet(line.substringAfter(". "))
            }
            else -> {
                if (paragraph.isNotEmpty()) paragraph.append(' ')
                paragraph.append(line)
            }
        }
        index += 1
    }
    flush()
    if (blocks.isEmpty() && source.isNotBlank()) blocks += MdBlock.Paragraph(source.trim())
    return blocks
}

private fun inlineMarkdown(source: String): AnnotatedString = buildAnnotatedString {
    var index = 0
    while (index < source.length) {
        when {
            source.startsWith("**", index) -> {
                val end = source.indexOf("**", index + 2)
                if (end < 0) {
                    append(source.substring(index))
                    return@buildAnnotatedString
                }
                withStyle(SpanStyle(fontWeight = FontWeight.SemiBold, color = Ink)) {
                    append(source.substring(index + 2, end))
                }
                index = end + 2
            }
            source[index] == '`' -> {
                val end = source.indexOf('`', index + 1)
                if (end < 0) {
                    append(source.substring(index))
                    return@buildAnnotatedString
                }
                withStyle(
                    SpanStyle(
                        fontFamily = FontFamily.Monospace,
                        background = CodeBg,
                        fontSize = 13.sp,
                        color = Ink,
                    ),
                ) {
                    append(source.substring(index + 1, end))
                }
                index = end + 1
            }
            source.startsWith("[", index) && source.indexOf("](", index) > 0 -> {
                val labelEnd = source.indexOf("](", index)
                val urlEnd = source.indexOf(')', labelEnd + 2)
                if (labelEnd < 0 || urlEnd < 0) {
                    append(source[index])
                    index += 1
                } else {
                    withStyle(SpanStyle(color = AccentDim, fontWeight = FontWeight.SemiBold)) {
                        append(source.substring(index + 1, labelEnd))
                    }
                    index = urlEnd + 1
                }
            }
            else -> {
                append(source[index])
                index += 1
            }
        }
    }
}
