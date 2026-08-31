import { Navigate, Route, Routes } from 'react-router-dom';

import KnowledgeLayout from './components/KnowledgeLayout';
import Layout from './components/Layout';
import ChatPage from './pages/ChatPage';
import ConversationsPage from './pages/ConversationsPage';
import KnowledgeAssistantPage from './pages/KnowledgeAssistantPage';
import KnowledgeEditorPage from './pages/KnowledgeEditorPage';
import KnowledgeGraphPage from './pages/KnowledgeGraphPage';
import KnowledgeListPage from './pages/KnowledgeListPage';
import KnowledgeReaderPage from './pages/KnowledgeReaderPage';
import KnowledgeSearchPage from './pages/KnowledgeSearchPage';
import ModesPage from './pages/ModesPage';
import SettingsPage from './pages/SettingsPage';
import SkillDetailPage from './pages/SkillDetailPage';
import SkillsPage from './pages/SkillsPage';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<ChatPage />} />
        <Route path="/chat/:id" element={<ChatPage />} />
        <Route path="/conversations" element={<ConversationsPage />} />
        <Route path="/modes" element={<ModesPage />} />
        <Route path="/skills" element={<SkillsPage />} />
        <Route path="/skills/:id" element={<SkillDetailPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
      <Route element={<KnowledgeLayout />}>
        <Route path="/knowledge" element={<KnowledgeListPage />} />
        <Route path="/knowledge/new" element={<KnowledgeEditorPage />} />
        <Route path="/knowledge/search" element={<KnowledgeSearchPage />} />
        <Route path="/knowledge/graph" element={<KnowledgeGraphPage />} />
        <Route path="/knowledge/assistant" element={<KnowledgeAssistantPage />} />
        <Route path="/knowledge/:id/edit" element={<KnowledgeEditorPage />} />
        <Route path="/knowledge/:id" element={<KnowledgeReaderPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
