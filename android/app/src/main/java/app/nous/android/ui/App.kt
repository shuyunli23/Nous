package app.nous.android.ui

import android.app.Application
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel

@Composable
fun AppRoot() {
    val app = LocalContext.current.applicationContext as Application
    val viewModel: NousViewModel = viewModel(
        factory = ViewModelProvider.AndroidViewModelFactory.getInstance(app),
    )
    val state by viewModel.state.collectAsStateWithLifecycle()
    val reading = state.panel == Panel.Skill || state.panel == Panel.Note
    SystemBars(lightBackground = state.booting || state.route != Route.Inbox || reading)
    when {
        state.booting -> BootScreen()
        state.route == Route.Connect -> ConnectScreen(
            url = state.serverUrl,
            connecting = state.connecting,
            error = state.connectError,
            onUrl = viewModel::updateServerUrl,
            onConnect = viewModel::connect,
        )
        state.route == Route.Chat -> ChatScreen(
            title = state.chatTitle,
            lines = state.lines,
            loading = state.chatLoading,
            draft = state.draft,
            sending = state.sending,
            statusLine = state.statusLine,
            error = state.chatError,
            modes = state.modes,
            selectedModeId = state.selectedModeId,
            freshChat = state.conversationId == null,
            onBack = viewModel::backToInbox,
            onDraft = viewModel::updateDraft,
            onSend = viewModel::send,
            onSelectMode = viewModel::selectMode,
        )
        else -> HomeShell(
            section = state.section,
            panel = state.panel,
            health = state.health,
            nowPlaying = state.tracks.find { it.id == state.playingId },
            playing = state.playing,
            onSection = viewModel::openSection,
            onBack = viewModel::closeDetail,
            onDisconnect = viewModel::disconnect,
            onToggle = {
                val track = state.tracks.find { it.id == state.playingId }
                if (track != null) viewModel.toggleTrack(track)
            },
        ) {
            when {
                state.panel == Panel.Skill -> SkillDetailScreen(
                    detail = state.skillDetail,
                    loading = state.skillsLoading,
                    error = state.skillsError,
                )
                state.panel == Panel.Note -> NoteReader(
                    detail = state.noteDetail,
                    loading = state.noteLoading,
                    error = state.notesError,
                )
                state.section == Section.Skills -> SkillsScreen(
                    skills = state.skills,
                    query = state.skillQuery,
                    loading = state.skillsLoading,
                    error = state.skillsError,
                    onQuery = viewModel::updateSkillQuery,
                    onSearch = viewModel::loadSkills,
                    onOpen = viewModel::openSkill,
                )
                state.section == Section.Nexus -> NexusScreen(
                    panel = state.panel,
                    notes = state.notes,
                    hits = state.searchHits,
                    query = state.noteQuery,
                    loading = state.notesLoading,
                    searching = state.searchLoading,
                    error = state.notesError,
                    askDraft = state.askDraft,
                    asking = state.asking,
                    askResult = state.askResult,
                    graph = state.graph,
                    graphLoading = state.graphLoading,
                    onPanel = viewModel::showPanel,
                    onQuery = viewModel::updateNoteQuery,
                    onSubmit = viewModel::submitNotes,
                    onOpen = viewModel::openNote,
                    onAskDraft = viewModel::updateAsk,
                    onAsk = viewModel::ask,
                )
                state.section == Section.Harmony -> HarmonyScreen(
                    tracks = state.tracks,
                    loading = state.tracksLoading,
                    error = state.tracksError,
                    playingId = state.playingId,
                    playing = state.playing,
                    onRefresh = viewModel::loadTracks,
                    onToggle = viewModel::toggleTrack,
                )
                else -> InboxScreen(
                    health = state.health,
                    conversations = state.conversations,
                    loading = state.listLoading,
                    error = state.listError,
                    embedded = true,
                    onRefresh = viewModel::refreshInbox,
                    onDisconnect = viewModel::disconnect,
                    onOpen = viewModel::openChat,
                    onDelete = viewModel::deleteConversation,
                    onNew = viewModel::newChat,
                )
            }
        }
    }
}

@Composable
private fun BootScreen() {
    Box(modifier = Modifier.fillMaxSize().background(Bg), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            NousMark()
            Spacer(Modifier.height(18.dp))
            CircularProgressIndicator(modifier = Modifier.size(22.dp), color = Accent, strokeWidth = 2.dp)
        }
    }
}
