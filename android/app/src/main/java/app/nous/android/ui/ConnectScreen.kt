package app.nous.android.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun ConnectScreen(
    url: String,
    connecting: Boolean,
    error: String?,
    onUrl: (String) -> Unit,
    onConnect: (String) -> Unit,
) {
    var password by rememberSaveable { mutableStateOf("") }
    val colors = OutlinedTextFieldDefaults.colors(
        focusedBorderColor = Accent,
        unfocusedBorderColor = BorderStrong,
        focusedLabelColor = AccentDim,
        cursorColor = Accent,
        focusedContainerColor = Color.White,
        unfocusedContainerColor = Color.White,
    )
    WorkspaceBackdrop {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .imePadding()
                .verticalScroll(rememberScrollState())
                .statusBarsPadding()
                .navigationBarsPadding()
                .padding(horizontal = 20.dp, vertical = 28.dp),
        ) {
            SurfaceCard {
                Text("NOUS", color = AccentDim, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, letterSpacing = 1.2.sp)
                Spacer(Modifier.height(14.dp))
                NousMark()
                Spacer(Modifier.height(14.dp))
                Text("解锁工作台", color = Ink, fontSize = 28.sp, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(6.dp))
                Text(
                    "对话、Skill、NexusMind 和 Harmony 用的是电脑上那一份。",
                    color = Dim,
                    fontSize = 14.sp,
                    lineHeight = 21.sp,
                )
                Spacer(Modifier.height(18.dp))
                OutlinedTextField(
                    value = url,
                    onValueChange = onUrl,
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("服务器地址") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Next),
                    shape = RoundedCornerShape(12.dp),
                    colors = colors,
                )
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("管理密码") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
                    keyboardActions = KeyboardActions(onDone = { if (!connecting) onConnect(password) }),
                    shape = RoundedCornerShape(12.dp),
                    colors = colors,
                )
                Spacer(Modifier.height(8.dp))
                Text(
                    "真机填电脑局域网地址，例如 http://10.119.145.233:8000。模拟器填 http://10.0.2.2:8000。密码没改过是 admin123。",
                    color = Faint,
                    fontSize = 12.sp,
                    lineHeight = 18.sp,
                )
                Spacer(Modifier.height(16.dp))
                Button(
                    onClick = { onConnect(password) },
                    enabled = !connecting,
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                    shape = RoundedCornerShape(14.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Accent, contentColor = Color.White),
                ) {
                    if (connecting) {
                        CircularProgressIndicator(modifier = Modifier.size(18.dp), color = Color.White, strokeWidth = 2.dp)
                    } else {
                        Text("解锁并连接", fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                    }
                }
                if (!error.isNullOrBlank()) {
                    Spacer(Modifier.height(12.dp))
                    Text(error, color = Danger, fontSize = 13.sp, lineHeight = 19.sp)
                }
            }
        }
    }
}
