package app.nous.android.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import android.media.AudioAttributes
import android.media.MediaPlayer
import app.nous.android.data.AskResult
import app.nous.android.data.ChatLine
import app.nous.android.data.ConversationItem
import app.nous.android.data.DEFAULT_SERVER
import app.nous.android.data.GraphGlance
import app.nous.android.data.ModeItem
import app.nous.android.data.NoteDetailItem
import app.nous.android.data.NoteItem
import app.nous.android.data.NousApi
import app.nous.android.data.NousApiException
import app.nous.android.data.ServerHealth
import app.nous.android.data.SessionStore
import app.nous.android.data.SkillDetailItem
import app.nous.android.data.SkillItem
import app.nous.android.data.StreamEvent
import app.nous.android.data.TrackItem
import java.io.IOException
import java.net.ConnectException
import java.net.NoRouteToHostException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

enum class Route { Connect, Inbox, Chat }

enum class Section { Nous, Skills, Nexus, Harmony }

enum class Panel { Browse, Search, Skill, Note, Ask, Graph }

data class NousUiState(
    val booting: Boolean = true,
    val route: Route = Route.Connect,
    val serverUrl: String = DEFAULT_SERVER,
    val health: ServerHealth? = null,
    val connecting: Boolean = false,
    val connectError: String? = null,
    val conversations: List<ConversationItem> = emptyList(),
    val listLoading: Boolean = false,
    val listError: String? = null,
    val section: Section = Section.Nous,
    val panel: Panel = Panel.Browse,
    val modes: List<ModeItem> = emptyList(),
    val selectedModeId: String? = null,
    val skills: List<SkillItem> = emptyList(),
    val skillsLoading: Boolean = false,
    val skillsError: String? = null,
    val skillQuery: String = "",
    val skillDetail: SkillDetailItem? = null,
    val notes: List<NoteItem> = emptyList(),
    val notesLoading: Boolean = false,
    val notesError: String? = null,
    val noteQuery: String = "",
    val searchHits: List<NoteItem> = emptyList(),
    val searchLoading: Boolean = false,
    val noteDetail: NoteDetailItem? = null,
    val noteLoading: Boolean = false,
    val askDraft: String = "",
    val askResult: AskResult? = null,
    val asking: Boolean = false,
    val graph: GraphGlance? = null,
    val graphLoading: Boolean = false,
    val tracks: List<TrackItem> = emptyList(),
    val tracksLoading: Boolean = false,
    val tracksError: String? = null,
    val playingId: String? = null,
    val playing: Boolean = false,
    val chatTitle: String = "新对话",
    val conversationId: String? = null,
    val lines: List<ChatLine> = emptyList(),
    val chatLoading: Boolean = false,
    val draft: String = "",
    val sending: Boolean = false,
    val statusLine: String? = null,
    val chatError: String? = null,
)

class NousViewModel(app: Application) : AndroidViewModel(app) {
    private val store = SessionStore(app)
    private val api = NousApi(store)
    private val _state = MutableStateFlow(NousUiState())
    val state: StateFlow<NousUiState> = _state.asStateFlow()

    private var sendJob: Job? = null
    private var chatEpoch = 0
    private var player: MediaPlayer? = null
    private var nexusBrowse = Panel.Browse

    init {
        val saved = store.baseUrl
        if (saved.isNullOrBlank()) {
            _state.update { it.copy(booting = false) }
        } else {
            _state.update { it.copy(serverUrl = saved) }
            viewModelScope.launch {
                try {
                    val health = withContext(Dispatchers.IO) { api.health() }
                    _state.update { it.copy(booting = false, route = Route.Inbox, health = health) }
                    refreshInbox()
                    loadModes()
                } catch (e: CancellationException) {
                    throw e
                } catch (_: Exception) {
                    _state.update { it.copy(booting = false) }
                }
            }
        }
    }

    fun updateServerUrl(value: String) {
        _state.update { it.copy(serverUrl = value, connectError = null) }
    }

    fun connect(password: String) {
        val url = _state.value.serverUrl
        viewModelScope.launch {
            _state.update { it.copy(connecting = true, connectError = null) }
            try {
                val health = withContext(Dispatchers.IO) { api.connect(url, password) }
                _state.update {
                    it.copy(
                        connecting = false,
                        route = Route.Inbox,
                        health = health,
                        serverUrl = store.baseUrl ?: url,
                    )
                }
                refreshInbox()
                loadModes()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.update { it.copy(connecting = false, connectError = friendly(e)) }
            }
        }
    }

    fun disconnect() {
        chatEpoch += 1
        sendJob?.cancel()
        api.cancelStream()
        api.clearHarmonyToken()
        releasePlayer()
        store.clearCookies()
        val url = _state.value.serverUrl
        _state.value = NousUiState(booting = false, serverUrl = url)
    }

    fun refreshInbox() {
        viewModelScope.launch {
            _state.update { it.copy(listLoading = true) }
            try {
                val items = withContext(Dispatchers.IO) { api.listConversations() }
                _state.update { state ->
                    if (state.route == Route.Connect) state.copy(listLoading = false)
                    else state.copy(listLoading = false, conversations = items, listError = null)
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.update { state ->
                    if (state.route == Route.Connect) state.copy(listLoading = false)
                    else state.copy(listLoading = false, listError = friendly(e))
                }
            }
        }
    }

    fun deleteConversation(id: String) {
        viewModelScope.launch {
            try {
                withContext(Dispatchers.IO) { api.deleteConversation(id) }
                _state.update { state ->
                    state.copy(conversations = state.conversations.filterNot { it.id == id })
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.update { it.copy(listError = friendly(e)) }
            }
        }
    }

    fun openChat(id: String) {
        val known = _state.value.conversations.find { it.id == id }?.title ?: "会话"
        chatEpoch += 1
        val epoch = chatEpoch
        _state.update {
            it.copy(
                route = Route.Chat,
                conversationId = id,
                chatTitle = known,
                lines = emptyList(),
                chatLoading = true,
                chatError = null,
                sending = false,
                statusLine = null,
                draft = "",
            )
        }
        sendJob?.cancel()
        api.cancelStream()
        viewModelScope.launch {
            try {
                val detail = withContext(Dispatchers.IO) { api.getConversation(id) }
                if (chatEpoch != epoch) return@launch
                _state.update {
                    it.copy(chatLoading = false, chatTitle = detail.title, lines = detail.lines)
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                if (chatEpoch != epoch) return@launch
                _state.update { it.copy(chatLoading = false, chatError = friendly(e)) }
            }
        }
    }

    fun newChat() {
        chatEpoch += 1
        _state.update {
            it.copy(
                route = Route.Chat,
                conversationId = null,
                chatTitle = "新对话",
                lines = emptyList(),
                chatLoading = false,
                chatError = null,
                sending = false,
                statusLine = null,
                draft = "",
            )
        }
        sendJob?.cancel()
        api.cancelStream()
    }

    fun backToInbox() {
        chatEpoch += 1
        _state.update {
            it.copy(
                route = Route.Inbox,
                section = Section.Nous,
                panel = Panel.Browse,
                sending = false,
                statusLine = null,
                chatError = null,
            )
        }
        sendJob?.cancel()
        api.cancelStream()
        refreshInbox()
    }

    fun updateDraft(value: String) {
        _state.update { it.copy(draft = value) }
    }

    fun send() {
        val snapshot = _state.value
        val text = snapshot.draft.trim()
        if (text.isEmpty() || snapshot.sending || snapshot.chatLoading) return
        val epoch = chatEpoch
        val userLine = ChatLine(id = "user-${System.nanoTime()}", role = "user", content = text)
        val pending = ChatLine(id = PENDING_ID, role = "assistant", content = "", pending = true)
        _state.update {
            it.copy(
                draft = "",
                sending = true,
                chatError = null,
                statusLine = "正在思考",
                lines = it.lines.filterNot { line -> line.id == PENDING_ID } + userLine + pending,
            )
        }
        sendJob?.cancel()
        sendJob = viewModelScope.launch {
            try {
                api.streamChat(
                    snapshot.conversationId,
                    text,
                    snapshot.selectedModeId.takeIf { snapshot.conversationId == null },
                ) { event ->
                    if (chatEpoch == epoch) applyEvent(event)
                }
                _state.update { state ->
                    if (!state.sending || chatEpoch != epoch) state
                    else state.copy(
                        sending = false,
                        statusLine = null,
                        lines = state.lines.map { line ->
                            if (line.id == PENDING_ID) line.copy(pending = false) else line
                        },
                    )
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                if (chatEpoch != epoch || !_state.value.sending || cancelled(e)) return@launch
                _state.update {
                    it.copy(
                        sending = false,
                        statusLine = null,
                        chatError = friendly(e),
                        draft = if (it.draft.isBlank()) text else it.draft,
                        lines = it.lines.map { line ->
                            if (line.id == PENDING_ID) line.copy(pending = false) else line
                        },
                    )
                }
            }
        }
    }

    fun openSection(section: Section) {
        if (section == Section.Nexus) nexusBrowse = Panel.Browse
        _state.update { it.copy(route = Route.Inbox, section = section, panel = Panel.Browse) }
        when (section) {
            Section.Nous -> if (_state.value.conversations.isEmpty()) refreshInbox()
            Section.Skills -> if (_state.value.skills.isEmpty()) loadSkills()
            Section.Nexus -> if (_state.value.notes.isEmpty()) loadNotes()
            Section.Harmony -> if (_state.value.tracks.isEmpty()) loadTracks()
        }
    }

    fun closeDetail() {
        val panel = when (_state.value.section) {
            Section.Nexus -> if (nexusBrowse == Panel.Note || nexusBrowse == Panel.Skill) Panel.Browse else nexusBrowse
            else -> Panel.Browse
        }
        showPanel(panel)
    }

    fun showPanel(panel: Panel) {
        if (panel == Panel.Browse || panel == Panel.Search || panel == Panel.Ask || panel == Panel.Graph) {
            nexusBrowse = panel
        }
        _state.update { it.copy(panel = panel, notesError = null, skillsError = null) }
        when (panel) {
            Panel.Browse -> if (_state.value.section == Section.Nexus && _state.value.notes.isEmpty()) loadNotes()
            Panel.Graph -> if (_state.value.graph == null) loadGraph()
            else -> Unit
        }
    }

    fun selectMode(id: String) {
        _state.update { it.copy(selectedModeId = if (it.selectedModeId == id) null else id) }
    }

    fun updateSkillQuery(value: String) {
        _state.update { it.copy(skillQuery = value, skillsError = null) }
    }

    fun loadSkills() {
        val query = _state.value.skillQuery
        viewModelScope.launch {
            _state.update { it.copy(skillsLoading = true) }
            try {
                val items = withContext(Dispatchers.IO) { api.listSkills(query) }
                _state.update { state ->
                    if (state.route == Route.Connect) state.copy(skillsLoading = false)
                    else state.copy(skillsLoading = false, skills = items, skillsError = null)
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.update { it.copy(skillsLoading = false, skillsError = friendly(e)) }
            }
        }
    }

    fun openSkill(id: String) {
        _state.update {
            it.copy(panel = Panel.Skill, skillDetail = null, skillsLoading = true, skillsError = null)
        }
        viewModelScope.launch {
            try {
                val detail = withContext(Dispatchers.IO) { api.getSkill(id) }
                _state.update { state ->
                    if (state.panel != Panel.Skill) state.copy(skillsLoading = false)
                    else state.copy(skillsLoading = false, skillDetail = detail, skillsError = null)
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.update { it.copy(skillsLoading = false, skillsError = friendly(e)) }
            }
        }
    }

    fun updateNoteQuery(value: String) {
        _state.update { it.copy(noteQuery = value, notesError = null) }
    }

    fun submitNotes() {
        val query = _state.value.noteQuery.trim()
        if (_state.value.panel == Panel.Search) {
            if (query.isEmpty()) {
                _state.update { it.copy(notesError = "先写一个检索词") }
                return
            }
            searchNotes(query)
        } else {
            loadNotes(query)
        }
    }

    fun loadNotes(query: String = _state.value.noteQuery) {
        viewModelScope.launch {
            _state.update { it.copy(notesLoading = true) }
            try {
                val items = withContext(Dispatchers.IO) { api.listKnowledge(query) }
                _state.update { state ->
                    if (state.route == Route.Connect) state.copy(notesLoading = false)
                    else state.copy(notesLoading = false, notes = items, notesError = null)
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.update { it.copy(notesLoading = false, notesError = friendly(e)) }
            }
        }
    }

    private fun searchNotes(query: String) {
        viewModelScope.launch {
            _state.update { it.copy(searchLoading = true) }
            try {
                val items = withContext(Dispatchers.IO) { api.searchKnowledge(query) }
                _state.update { it.copy(searchLoading = false, searchHits = items, notesError = null) }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.update { it.copy(searchLoading = false, notesError = friendly(e)) }
            }
        }
    }

    fun openNote(id: String) {
        _state.update {
            it.copy(panel = Panel.Note, noteDetail = null, noteLoading = true, notesError = null)
        }
        viewModelScope.launch {
            try {
                val detail = withContext(Dispatchers.IO) { api.getKnowledge(id) }
                _state.update { state ->
                    if (state.panel != Panel.Note) state.copy(noteLoading = false)
                    else state.copy(noteLoading = false, noteDetail = detail, notesError = null)
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.update { it.copy(noteLoading = false, notesError = friendly(e)) }
            }
        }
    }

    fun updateAsk(value: String) {
        _state.update { it.copy(askDraft = value, notesError = null) }
    }

    fun ask() {
        val question = _state.value.askDraft.trim()
        if (question.isEmpty() || _state.value.asking) return
        viewModelScope.launch {
            _state.update { it.copy(asking = true, notesError = null) }
            try {
                val result = withContext(Dispatchers.IO) { api.askKnowledge(question) }
                _state.update { it.copy(asking = false, askResult = result, askDraft = "") }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.update { it.copy(asking = false, notesError = friendly(e)) }
            }
        }
    }

    fun loadGraph() {
        viewModelScope.launch {
            _state.update { it.copy(graphLoading = true) }
            try {
                val graph = withContext(Dispatchers.IO) { api.knowledgeGraph() }
                _state.update { it.copy(graphLoading = false, graph = graph, notesError = null) }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.update { it.copy(graphLoading = false, notesError = friendly(e)) }
            }
        }
    }

    fun loadTracks() {
        viewModelScope.launch {
            _state.update { it.copy(tracksLoading = true) }
            try {
                val tracks = withContext(Dispatchers.IO) { api.listTracks() }
                _state.update { state ->
                    if (state.route == Route.Connect) state.copy(tracksLoading = false)
                    else state.copy(tracksLoading = false, tracks = tracks, tracksError = null)
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.update { it.copy(tracksLoading = false, tracksError = friendly(e)) }
            }
        }
    }

    fun toggleTrack(track: TrackItem) {
        val current = player
        if (_state.value.playingId == track.id && current != null) {
            val playingNow = runCatching { current.isPlaying }.getOrDefault(false)
            if (playingNow) {
                current.pause()
                _state.update { it.copy(playing = false) }
            } else if (runCatching { current.currentPosition }.isSuccess) {
                current.start()
                _state.update { it.copy(playing = true) }
            }
            return
        }
        viewModelScope.launch {
            _state.update { it.copy(playingId = track.id, playing = false, tracksError = null) }
            try {
                val url = withContext(Dispatchers.IO) { api.trackStreamUrl(track.id) }
                startPlayer(track.id, url)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.update { it.copy(playing = false, tracksError = friendly(e)) }
            }
        }
    }

    private fun startPlayer(id: String, url: String) {
        releasePlayer()
        val media = MediaPlayer()
        media.setAudioAttributes(
            AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                .build(),
        )
        media.setOnPreparedListener { player ->
            if (this.player !== player) return@setOnPreparedListener
            player.start()
            _state.update { it.copy(playing = true, playingId = id) }
        }
        media.setOnCompletionListener {
            _state.update { state -> if (state.playingId == id) state.copy(playing = false) else state }
        }
        media.setOnErrorListener { _, _, _ ->
            _state.update { it.copy(playing = false, tracksError = "这首暂时播不了") }
            true
        }
        try {
            media.setDataSource(url)
            media.prepareAsync()
            player = media
        } catch (e: Exception) {
            media.release()
            _state.update { it.copy(playing = false, tracksError = friendly(e)) }
        }
    }

    private fun releasePlayer() {
        player?.run {
            setOnPreparedListener(null)
            setOnCompletionListener(null)
            setOnErrorListener(null)
            runCatching { stop() }
            release()
        }
        player = null
    }

    private fun loadModes() {
        viewModelScope.launch {
            try {
                val modes = withContext(Dispatchers.IO) { api.listModes() }
                _state.update { state ->
                    if (state.route == Route.Connect) state else state.copy(modes = modes)
                }
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                // Modes are optional. Chat still works without a chip selected.
            }
        }
    }

    override fun onCleared() {
        sendJob?.cancel()
        api.cancelStream()
        releasePlayer()
    }

    private fun applyEvent(event: StreamEvent) {
        when (event) {
            is StreamEvent.Started -> _state.update {
                it.copy(
                    conversationId = event.conversationId.ifBlank { it.conversationId },
                    statusLine = it.statusLine ?: "正在思考",
                )
            }
            is StreamEvent.Status -> _state.update { it.copy(statusLine = event.title) }
            is StreamEvent.Token -> updatePending(status = null) { it.copy(content = it.content + event.text) }
            StreamEvent.Clear -> updatePending { it.copy(content = "") }
            is StreamEvent.Done -> _state.update { state ->
                state.copy(
                    sending = false,
                    statusLine = null,
                    conversationId = event.conversationId.ifBlank { state.conversationId },
                    chatTitle = event.title ?: state.chatTitle,
                    lines = state.lines.map { line ->
                        if (line.id != PENDING_ID) line
                        else line.copy(
                            id = event.messageId.ifBlank { "assistant-${System.nanoTime()}" },
                            content = event.answer.ifBlank { line.content },
                            skills = event.skills,
                            pending = false,
                        )
                    },
                )
            }
        }
    }

    private fun updatePending(status: String? = _state.value.statusLine, block: (ChatLine) -> ChatLine) {
        _state.update { state ->
            state.copy(
                statusLine = status,
                lines = state.lines.map { line -> if (line.id == PENDING_ID) block(line) else line },
            )
        }
    }

    private companion object {
        const val PENDING_ID = "pending-assistant"
        const val UNREACHABLE = "连不上服务器。确认后端已启动，手机和电脑在同一网络，并允许 8000 端口。"

        fun friendly(error: Throwable): String {
            var current: Throwable? = error
            while (current != null) {
                when (current) {
                    is NousApiException -> return current.message ?: "请求失败"
                    is SocketTimeoutException -> return "服务器太久没有响应"
                    is ConnectException, is UnknownHostException, is NoRouteToHostException -> return UNREACHABLE
                }
                current = current.cause
            }
            val message = error.message.orEmpty()
            if (
                message.contains("Failed to connect", ignoreCase = true) ||
                message.contains("Unable to resolve", ignoreCase = true)
            ) {
                return UNREACHABLE
            }
            return message.ifBlank { "出了点问题" }
        }

        fun cancelled(error: Throwable): Boolean {
            var current: Throwable? = error
            while (current != null) {
                if (current is IOException && current.message?.contains("Canceled", ignoreCase = true) == true) {
                    return true
                }
                current = current.cause
            }
            return false
        }
    }
}
