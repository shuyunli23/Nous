package app.nous.android.data

import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import okhttp3.Call
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject
import java.util.concurrent.TimeUnit
import kotlin.coroutines.coroutineContext

/**
 * Talks to the Nous FastAPI in this repo.
 *
 * A phone is not loopback, so it unlocks with the admin password and keeps the
 * `nous_owner` cookie. `X-User-Id: local-dev` is the same identity the web UI
 * sends, so conversations and Skills stay on one account.
 */
class NousApi(private val store: SessionStore) {
    private val jsonType = "application/json; charset=utf-8".toMediaType()
    private val client = OkHttpClient.Builder()
        .cookieJar(store.cookies)
        .connectTimeout(12, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .writeTimeout(20, TimeUnit.SECONDS)
        .build()
    private val streamClient = client.newBuilder()
        .readTimeout(130, TimeUnit.SECONDS)
        .build()

    private val streamGeneration = AtomicInteger()

    @Volatile
    private var streamCall: Call? = null

    fun cancelStream() {
        streamGeneration.incrementAndGet()
        streamCall?.cancel()
    }

    fun connect(rawUrl: String, password: String): ServerHealth {
        val root = normalizeBaseUrl(rawUrl)
        if (password.isBlank()) throw NousApiException("请填写管理密码")
        val request = Request.Builder()
            .url(endpoint(root, "/auth/unlock"))
            .nous()
            .post(JSONObject().put("password", password).toBody())
            .build()
        execute(request)
        val health = readHealth(root)
        store.baseUrl = root
        return health
    }

    fun health(): ServerHealth = readHealth(requireRoot())

    fun listConversations(): List<ConversationItem> {
        val json = get("/conversations", mapOf("limit" to "50", "offset" to "0"))
        val items = json.optJSONArray("items") ?: JSONArray()
        return List(items.length()) { index ->
            val item = items.getJSONObject(index)
            ConversationItem(
                id = item.getString("id"),
                title = item.optString("title").ifBlank { "未命名会话" },
                modeName = item.optString("mode_name").ifBlank { null },
                messageCount = item.optInt("message_count"),
                updatedAt = item.optString("updated_time"),
            )
        }
    }

    fun getConversation(id: String): ConversationDetail {
        val json = get("/conversations/$id")
        val messages = json.optJSONArray("messages") ?: JSONArray()
        val lines = List(messages.length()) { index ->
            val message = messages.getJSONObject(index)
            ChatLine(
                id = message.getString("id"),
                role = message.optString("role"),
                content = message.optString("content"),
                seq = message.optInt("seq"),
            )
        }.sortedBy { it.seq }
        return ConversationDetail(
            id = json.getString("id"),
            title = json.optString("title").ifBlank { "未命名会话" },
            lines = lines,
        )
    }

    fun deleteConversation(id: String) {
        val request = Request.Builder()
            .url(endpoint(requireRoot(), "/conversations/$id"))
            .nous()
            .delete()
            .build()
        execute(request)
    }

    fun listModes(): List<ModeItem> {
        val items = getArray("/chat-modes")
        return List(items.length()) { index ->
            val item = items.getJSONObject(index)
            ModeItem(
                id = item.getString("id"),
                name = item.optString("name").ifBlank { "未命名模式" },
                description = item.optString("description"),
            )
        }
    }

    fun listSkills(search: String? = null): List<SkillItem> {
        val query = mutableMapOf("limit" to "50", "offset" to "0")
        if (!search.isNullOrBlank()) query["search"] = search.trim()
        val items = get("/skills", query).optJSONArray("items") ?: JSONArray()
        return List(items.length()) { index ->
            val item = items.getJSONObject(index)
            SkillItem(
                id = item.getString("id"),
                name = item.optString("name").ifBlank { "未命名 Skill" },
                description = item.optString("description"),
                status = item.optString("status"),
                keywords = joinStrings(item.optJSONArray("trigger_keywords")),
            )
        }
    }

    fun getSkill(id: String): SkillDetailItem {
        val item = get("/skills/$id")
        return SkillDetailItem(
            id = item.getString("id"),
            name = item.optString("name").ifBlank { "未命名 Skill" },
            description = item.optString("description"),
            status = item.optString("status"),
            instruction = item.optString("instruction"),
            keywords = joinStrings(item.optJSONArray("trigger_keywords")),
        )
    }

    fun listKnowledge(queryText: String? = null): List<NoteItem> {
        val query = mutableMapOf("page" to "1", "page_size" to "40")
        if (!queryText.isNullOrBlank()) query["q"] = queryText.trim()
        return notesFrom(get("/knowledge", query).optJSONArray("items"))
    }

    fun searchKnowledge(queryText: String): List<NoteItem> {
        val json = get(
            "/search",
            mapOf("q" to queryText.trim(), "mode" to "hybrid", "page" to "1", "page_size" to "30"),
        )
        return notesFrom(json.optJSONArray("items") ?: json.optJSONArray("hits"))
    }

    fun getKnowledge(id: String): NoteDetailItem {
        val item = get("/knowledge/$id")
        return NoteDetailItem(
            id = item.getString("id"),
            title = item.optString("title").ifBlank { "未命名笔记" },
            summary = item.optString("summary"),
            category = item.optString("category").ifBlank { null },
            markdown = item.optString("markdown_content"),
        )
    }

    fun askKnowledge(message: String): AskResult {
        val json = JSONObject(execute(nousPost("/assistant/ask", JSONObject().put("message", message))))
        val citations = json.optJSONArray("citations")
        return AskResult(
            answer = json.optString("answer"),
            citations = if (citations == null) {
                emptyList()
            } else {
                List(citations.length()) { index -> citations.getJSONObject(index).optString("title") }
                    .filter { it.isNotBlank() }
            },
        )
    }

    fun knowledgeGraph(): GraphGlance {
        val json = get("/graph", mapOf("max_keywords" to "24", "max_knowledge" to "24"))
        val stats = json.optJSONObject("stats")
        val nodes = json.optJSONArray("nodes") ?: JSONArray()
        val labels = List(nodes.length()) { index ->
            val node = nodes.getJSONObject(index)
            val kind = when (node.optString("type")) {
                "keyword" -> "关键词"
                "category" -> "分类"
                else -> "笔记"
            }
            "$kind · ${node.optString("label")}"
        }.filter { it.substringAfter("· ").isNotBlank() }.take(40)
        return GraphGlance(
            knowledge = stats?.optInt("knowledge") ?: 0,
            keywords = stats?.optInt("keyword") ?: 0,
            categories = stats?.optInt("category") ?: 0,
            labels = labels,
        )
    }

    fun listTracks(): List<TrackItem> {
        val token = harmonyToken()
        val request = Request.Builder()
            .url(origin("/api/music"))
            .header("Authorization", "Bearer $token")
            .get()
            .build()
        val items = JSONArray(execute(request))
        return List(items.length()) { index ->
            val item = items.getJSONObject(index)
            TrackItem(
                id = item.getString("id"),
                title = item.optString("title").ifBlank { "未命名曲目" },
                artist = item.optString("artist").ifBlank { "未知艺术家" },
                album = item.optString("album").ifBlank { null },
                durationSec = item.optInt("duration"),
            )
        }
    }

    fun trackStreamUrl(id: String): String {
        val token = cachedHarmonyToken ?: harmonyToken()
        return origin("/api/music/$id/stream")
            .newBuilder()
            .addQueryParameter("token", token)
            .build()
            .toString()
    }

    private var cachedHarmonyToken: String? = null

    private fun harmonyToken(): String {
        cachedHarmonyToken?.let { return it }
        val ticket = JSONObject(execute(nousPost("/harmony/sso", JSONObject()))).getString("ticket")
        val login = Request.Builder()
            .url(origin("/api/auth/sso"))
            .header("Content-Type", "application/json")
            .post(JSONObject().put("ticket", ticket).toBody())
            .build()
        val token = JSONObject(execute(login)).getString("access_token")
        cachedHarmonyToken = token
        return token
    }

    fun clearHarmonyToken() {
        cachedHarmonyToken = null
    }

    suspend fun streamChat(
        conversationId: String?,
        message: String,
        modeId: String? = null,
        onEvent: (StreamEvent) -> Unit,
    ) {
        val generation = streamGeneration.get()
        withContext(Dispatchers.IO) {
            val payload = JSONObject().put("message", message)
            if (conversationId.isNullOrBlank()) payload.put("conversation_id", JSONObject.NULL)
            else payload.put("conversation_id", conversationId)
            if (conversationId.isNullOrBlank() && !modeId.isNullOrBlank()) payload.put("mode_id", modeId)
            val request = Request.Builder()
                .url(endpoint(requireRoot(), "/chat/stream"))
                .header("Accept", "text/event-stream")
                .header("X-User-Id", USER_ID)
                .post(payload.toBody())
                .build()
            val call = streamClient.newCall(request)
            streamCall = call
            if (streamGeneration.get() != generation) call.cancel()
            var sawDone = false
            try {
                call.execute().use { response ->
                    if (!response.isSuccessful) {
                        throw errorFrom(response.code, response.body?.string().orEmpty())
                    }
                    val type = response.header("Content-Type").orEmpty()
                    val body = response.body ?: throw NousApiException("回复是空的")
                    if (!type.contains("text/event-stream")) {
                        throw NousApiException(body.string().ifBlank { "服务器没有按流式回复" })
                    }
                    val source = body.source()
                    var dataLines = mutableListOf<String>()
                    while (true) {
                        coroutineContext.ensureActive()
                        val line = source.readUtf8Line() ?: break
                        if (line.isEmpty()) {
                            val event = parseSse(dataLines)
                            dataLines = mutableListOf()
                            if (event != null) {
                                if (event is StreamEvent.Done) sawDone = true
                                withContext(Dispatchers.Main) { onEvent(event) }
                            }
                        } else if (!line.startsWith(":")) {
                            dataLines.add(line)
                        }
                    }
                    if (!sawDone) throw NousApiException("回复中断了，可以再发一次")
                }
            } finally {
                if (streamCall === call) streamCall = null
            }
        }
    }

    private fun readHealth(root: String): ServerHealth {
        val request = Request.Builder().url(endpoint(root, "/health")).nous().get().build()
        val json = JSONObject(execute(request))
        return ServerHealth(
            llmConfigured = json.optBoolean("llm_configured"),
            model = json.optString("llm_model"),
            provider = json.optString("llm_provider"),
        )
    }

    private fun get(path: String, query: Map<String, String> = emptyMap()): JSONObject {
        val request = Request.Builder().url(endpoint(requireRoot(), path, query)).nous().get().build()
        return JSONObject(execute(request))
    }

    private fun getArray(path: String): JSONArray {
        val request = Request.Builder().url(endpoint(requireRoot(), path)).nous().get().build()
        return JSONArray(execute(request))
    }

    private fun nousPost(path: String, body: JSONObject): Request {
        return Request.Builder()
            .url(endpoint(requireRoot(), path))
            .nous()
            .post(body.toBody())
            .build()
    }

    private fun notesFrom(items: JSONArray?): List<NoteItem> {
        if (items == null) return emptyList()
        return List(items.length()) { index ->
            val item = items.getJSONObject(index)
            NoteItem(
                id = item.getString("id"),
                title = item.optString("title").ifBlank { "未命名笔记" },
                summary = item.optString("summary").ifBlank { item.optString("snippet") },
                category = item.optString("category").ifBlank { null },
            )
        }
    }

    private fun joinStrings(array: JSONArray?): String {
        if (array == null || array.length() == 0) return ""
        return List(array.length()) { index -> array.optString(index) }
            .filter { it.isNotBlank() }
            .joinToString("、")
    }

    private fun origin(path: String, query: Map<String, String> = emptyMap()): HttpUrl {
        val builder = requireRoot().toHttpUrl().newBuilder()
        path.trim('/').split('/').filter { it.isNotEmpty() }.forEach { builder.addPathSegment(it) }
        query.forEach { (key, value) -> builder.addQueryParameter(key, value) }
        return builder.build()
    }

    private fun execute(request: Request): String {
        client.newCall(request).execute().use { response ->
            val text = response.body?.string().orEmpty()
            if (!response.isSuccessful) throw errorFrom(response.code, text)
            return text
        }
    }

    private fun errorFrom(status: Int, text: String): NousApiException {
        val error = try {
            JSONObject(text).optJSONObject("error")
        } catch (_: JSONException) {
            null
        }
        val message = when (error?.optString("code")) {
            "unauthorized" -> "密码不对"
            "owner_only" -> "需要管理密码才能从这台设备进入"
            else -> error?.optString("message")?.takeIf { it.isNotBlank() }
                ?: error?.optString("detail")?.takeIf { it.isNotBlank() }
                ?: "请求失败（$status）"
        }
        return NousApiException(message, status)
    }

    private fun parseSse(lines: List<String>): StreamEvent? {
        if (lines.isEmpty()) return null
        val data = lines
            .filter { it.startsWith("data:") }
            .joinToString("\n") { it.removePrefix("data:").trimStart() }
            .trim()
        if (data.isEmpty()) return null
        val json = try {
            JSONObject(data)
        } catch (_: JSONException) {
            throw NousApiException("回复格式异常")
        }
        return when (json.optString("type")) {
            "start" -> StreamEvent.Started(json.optString("conversation_id"))
            "token" -> StreamEvent.Token(json.optString("text"))
            "token_clear" -> StreamEvent.Clear
            "step_start" -> StreamEvent.Status(json.optString("title").ifBlank { "处理中" })
            "done" -> StreamEvent.Done(
                conversationId = json.optString("conversation_id"),
                messageId = json.optString("message_id"),
                answer = json.optString("answer"),
                title = json.optString("title").ifBlank { null },
                skills = readSkills(json.optJSONArray("used_skills")),
            )
            "error" -> throw NousApiException(json.optString("message").ifBlank { "对话失败" })
            else -> null
        }
    }

    private fun readSkills(array: JSONArray?): List<String> {
        if (array == null) return emptyList()
        return List(array.length()) { index -> array.getJSONObject(index).optString("name") }
            .filter { it.isNotBlank() }
    }

    private fun requireRoot(): String = store.baseUrl ?: throw NousApiException("还没有连接服务器")

    private fun endpoint(root: String, path: String, query: Map<String, String> = emptyMap()): HttpUrl {
        val builder = root.toHttpUrl().newBuilder().addPathSegment("api").addPathSegment("v1")
        path.trim('/').split('/').filter { it.isNotEmpty() }.forEach { builder.addPathSegment(it) }
        query.forEach { (key, value) -> builder.addQueryParameter(key, value) }
        return builder.build()
    }

    private fun Request.Builder.nous(): Request.Builder {
        return header("Accept", "application/json").header("X-User-Id", USER_ID)
    }

    private fun JSONObject.toBody() = toString().toRequestBody(jsonType)

    companion object {
        const val USER_ID = "local-dev"

        fun normalizeBaseUrl(raw: String): String {
            var value = raw.trim().trimEnd('/')
            if (value.isBlank()) throw NousApiException("请填写服务器地址")
            if (!value.startsWith("http://") && !value.startsWith("https://")) {
                value = "http://$value"
            }
            if (value.endsWith("/api/v1")) value = value.removeSuffix("/api/v1")
            if (value.endsWith("/api")) value = value.removeSuffix("/api")
            value = value.trimEnd('/')
            try {
                value.toHttpUrl()
            } catch (_: IllegalArgumentException) {
                throw NousApiException("地址格式不对")
            }
            return value
        }
    }
}

class NousApiException(message: String, val status: Int = 0) : Exception(message)
