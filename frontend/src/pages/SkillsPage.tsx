import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { ApiError } from '../api/client';
import {
  createSkill,
  deleteSkill,
  getSkill,
  importPackArchive,
  importPluginUrl,
  importSkillPack,
  listInstalledPacks,
  listSkillPacks,
  listSkills,
  previewPackArchive,
  previewPluginUrl,
  reindexSkills,
  searchSkills,
  setInstalledPackStatus,
  setSkillStatus,
  uninstallPack,
  updateSkill,
  type InstalledPackSummary,
  type PackArchivePreview,
  type SkillPackSummary,
} from '../api/skills';
import type {
  SkillCreatePayload,
  SkillDetail,
  SkillSearchResult,
  SkillStatus,
  SkillSummary,
} from '../api/types';
import SkillEditor from '../components/SkillEditor';
import { useI18n, type MessageKey } from '../i18n';

const PAGE_SIZE = 15;

const STATUS_KEY: Record<SkillStatus, MessageKey> = {
  draft: 'status.draft',
  active: 'status.active',
  disabled: 'status.disabled',
  deprecated: 'status.deprecated',
};

export default function SkillsPage() {
  const { t, formatDate } = useI18n();
  const navigate = useNavigate();
  const [items, setItems] = useState<SkillSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<SkillStatus | ''>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<SkillDetail | null>(null);
  const [saving, setSaving] = useState(false);
  const [editorError, setEditorError] = useState<string | null>(null);

  const [probeQuery, setProbeQuery] = useState('');
  const [probeResults, setProbeResults] = useState<SkillSearchResult[] | null>(
    null,
  );
  const [probing, setProbing] = useState(false);
  const [packs, setPacks] = useState<SkillPackSummary[]>([]);
  const [importingId, setImportingId] = useState<string | null>(null);
  const [importJson, setImportJson] = useState('');
  const [installedPacks, setInstalledPacks] = useState<InstalledPackSummary[]>(
    [],
  );
  const [zipPreview, setZipPreview] = useState<PackArchivePreview | null>(null);
  const [zipFile, setZipFile] = useState<File | null>(null);
  const [zipGrants, setZipGrants] = useState<string[]>([]);
  const [zipBusy, setZipBusy] = useState(false);
  const [pluginUrl, setPluginUrl] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await listSkills({
        limit: PAGE_SIZE,
        offset,
        status: statusFilter || undefined,
        search: search || undefined,
      });
      setItems(page.items);
      setTotal(page.total);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('skills.loadListFailed'));
    } finally {
      setLoading(false);
    }
  }, [offset, search, statusFilter, t]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    listSkillPacks()
      .then((res) => setPacks(res.items))
      .catch(() => setPacks([]));
    listInstalledPacks()
      .then(setInstalledPacks)
      .catch(() => setInstalledPacks([]));
  }, []);

  async function refreshInstalledPacks() {
    try {
      setInstalledPacks(await listInstalledPacks());
    } catch {
      /* ignore */
    }
  }

  async function handleZipSelected(file: File | null) {
    setZipFile(file);
    setZipPreview(null);
    setZipGrants([]);
    if (!file) return;
    setZipBusy(true);
    setError(null);
    try {
      const preview = await previewPackArchive(file);
      setZipPreview(preview);
      setZipGrants([...preview.permissions_requested]);
      if (preview.errors.length) {
        setError(t('skills.packInvalid', { errors: preview.errors.join('；') }));
      }
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('skills.zipPreviewFailed'));
    } finally {
      setZipBusy(false);
    }
  }

  async function handleImportZip() {
    if (!zipFile || !zipPreview || zipPreview.errors.length) return;
    setZipBusy(true);
    setError(null);
    try {
      const result = await importPackArchive(zipFile, {
        grant_permissions: zipGrants,
        activate: true,
        replace_existing: true,
      });
      setNotice(
        t('skills.installed', {
          name: result.pack.name,
          version: result.pack.version,
          skills: result.created_skills.length,
          tools: result.pack.tool_count,
        }),
      );
      setZipFile(null);
      setZipPreview(null);
      setZipGrants([]);
      setPluginUrl('');
      await load();
      await refreshInstalledPacks();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('skills.installFailed'));
    } finally {
      setZipBusy(false);
    }
  }

  async function handleUrlPreview() {
    const url = pluginUrl.trim();
    if (!url) return;
    setZipFile(null);
    setZipPreview(null);
    setZipGrants([]);
    setZipBusy(true);
    setError(null);
    try {
      const preview = await previewPluginUrl(url);
      setZipPreview(preview);
      setZipGrants([...preview.permissions_requested]);
      if (preview.errors.length) {
        setError(t('skills.packInvalid', { errors: preview.errors.join('；') }));
      }
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('skills.pluginPreviewFailed'));
    } finally {
      setZipBusy(false);
    }
  }

  async function handleUrlInstall() {
    const url = pluginUrl.trim();
    if (!url || !zipPreview || zipPreview.errors.length) return;
    setZipBusy(true);
    setError(null);
    try {
      const result = await importPluginUrl(url, {
        grant_permissions: zipGrants,
        activate: true,
        replace_existing: true,
      });
      setNotice(
        t('skills.installed', {
          name: result.pack.name,
          version: result.pack.version,
          skills: result.created_skills.length,
          tools: result.pack.tool_count,
        }),
      );
      setPluginUrl('');
      setZipFile(null);
      setZipPreview(null);
      setZipGrants([]);
      await load();
      await refreshInstalledPacks();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('skills.installFailed'));
    } finally {
      setZipBusy(false);
    }
  }

  function toggleGrant(perm: string) {
    setZipGrants((prev) =>
      prev.includes(perm) ? prev.filter((p) => p !== perm) : [...prev, perm],
    );
  }

  async function openEditor(id?: string) {
    setEditorError(null);
    if (!id) {
      setEditing(null);
      setEditorOpen(true);
      return;
    }
    try {
      const detail = await getSkill(id);
      setEditing(detail);
      setEditorOpen(true);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('skills.loadFailed'));
    }
  }

  async function handleSave(payload: SkillCreatePayload) {
    setSaving(true);
    setEditorError(null);
    try {
      if (editing) {
        await updateSkill(editing.id, payload);
        setNotice(t('skills.updated', { name: payload.name }));
      } else {
        await createSkill(payload);
        setNotice(t('skills.created', { name: payload.name }));
      }
      setEditorOpen(false);
      setEditing(null);
      await load();
    } catch (err: unknown) {
      setEditorError(err instanceof ApiError ? err.message : t('skills.saveFailed'));
    } finally {
      setSaving(false);
    }
  }

  async function toggleStatus(skill: SkillSummary) {
    const next: SkillStatus = skill.status === 'active' ? 'disabled' : 'active';
    setBusyId(skill.id);
    setError(null);
    try {
      await setSkillStatus(skill.id, next);
      setNotice(
        t('skills.toggled', {
          name: skill.name,
          action:
            next === 'active' ? t('common.enable') : t('common.disable'),
        }),
      );
      await load();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('skills.statusFailed'));
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(skill: SkillSummary) {
    if (!window.confirm(t('skills.confirmDelete', { name: skill.name }))) return;
    setBusyId(skill.id);
    setError(null);
    try {
      await deleteSkill(skill.id);
      setNotice(t('skills.deleted'));
      await load();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('skills.deleteFailed'));
    } finally {
      setBusyId(null);
    }
  }

  async function handleReindex() {
    setError(null);
    setNotice(null);
    try {
      const result = await reindexSkills(true);
      setNotice(
        t('skills.reindexed', {
          indexed: result.indexed,
          skipped: result.skipped,
          total: result.indexed_total,
          provider: result.embedding_provider,
          backend: result.vector_backend,
        }),
      );
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('skills.reindexFailed'));
    }
  }

  async function handleImportPack(packId: string) {
    setImportingId(packId);
    setError(null);
    try {
      const result = await importSkillPack({ pack_id: packId, activate: true });
      setNotice(
        t('skills.imported', {
          name: result.pack_name,
          created: result.total_created,
        }) +
          (result.total_skipped
            ? t('skills.importedSkipped', { skipped: result.total_skipped })
            : ''),
      );
      await load();
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('skills.importPackFailed'));
    } finally {
      setImportingId(null);
    }
  }

  async function handleImportJson() {
    setError(null);
    try {
      const parsed = JSON.parse(importJson) as {
        skills?: SkillCreatePayload[];
        name?: string;
      };
      if (!parsed.skills?.length) {
        setError(t('skills.jsonNeedSkills'));
        return;
      }
      const result = await importSkillPack({
        skills: parsed.skills,
        activate: true,
      });
      setNotice(
        t('skills.jsonImported', {
          created: result.total_created,
          skipped: result.total_skipped,
        }),
      );
      setImportJson('');
      await load();
    } catch (err: unknown) {
      setError(
        err instanceof ApiError
          ? err.message
          : err instanceof SyntaxError
            ? t('skills.jsonInvalid')
            : t('skills.importFailed'),
      );
    }
  }

  async function handleProbe(event: React.FormEvent) {
    event.preventDefault();
    if (!probeQuery.trim()) return;
    setProbing(true);
    setError(null);
    try {
      const response = await searchSkills(probeQuery.trim(), 5);
      setProbeResults(response.results);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : t('skills.probeFailed'));
    } finally {
      setProbing(false);
    }
  }

  const pageStart = total === 0 ? 0 : offset + 1;
  const pageEnd = offset + items.length;

  return (
    <div className="page">
      <div className="page__header">
        <div>
          <h1 className="page__title">Skills</h1>
          <p className="page__subtitle">
            {t('skills.subtitle', { total })}
          </p>
        </div>
        <div className="row">
          <button type="button" className="btn btn--sm" onClick={handleReindex}>
            {t('skills.reindex')}
          </button>
          <button
            type="button"
            className="btn btn--sm btn--primary"
            onClick={() => void openEditor()}
          >
            {t('skills.create')}
          </button>
        </div>
      </div>

      {error && <div className="alert alert--error">{error}</div>}
      {notice && <div className="alert alert--info">{notice}</div>}

      <section className="pack-section">
          <div className="pack-section__head">
            <h2 className="section__title">{t('skills.marketTitle')}</h2>
            <p className="muted" style={{ margin: 0, fontSize: 13 }}>
              {t('skills.marketLead')}
            </p>
          </div>
          {packs.length > 0 && (
          <div className="pack-grid">
            {packs.map((pack) => (
              <article key={pack.id} className="pack-card">
                <div className="pack-card__top">
                  <h3 className="pack-card__name">{pack.name}</h3>
                  <span className="pack-card__count">
                    {t('skills.skillCount', { count: pack.skill_count })}
                  </span>
                </div>
                <p className="pack-card__desc">{pack.description}</p>
                <div className="pack-card__tags">
                  {pack.tags.map((tag) => (
                    <span key={tag} className="keyword">
                      {tag}
                    </span>
                  ))}
                </div>
                <button
                  type="button"
                  className="btn btn--sm btn--primary"
                  disabled={importingId === pack.id}
                  onClick={() => void handleImportPack(pack.id)}
                >
                  {importingId === pack.id
                    ? t('skills.importing')
                    : t('skills.importActivate')}
                </button>
              </article>
            ))}
          </div>
          )}

          <div className="card" style={{ marginTop: 14 }}>
            <h3 style={{ marginTop: 0, fontSize: 15 }}>
              {t('skills.pluginTitle')}
            </h3>
            <p className="field__hint" style={{ marginTop: 0 }}>
              {t('skills.pluginHint')}
            </p>
            <form
              className="row"
              style={{ marginTop: 10, flexWrap: 'wrap' }}
              onSubmit={(e) => {
                e.preventDefault();
                void handleUrlPreview();
              }}
            >
              <input
                type="url"
                value={pluginUrl}
                onChange={(e) => setPluginUrl(e.target.value)}
                placeholder={t('skills.pluginUrlPlaceholder')}
                aria-label={t('skills.pluginUrlPlaceholder')}
                style={{ flex: '1 1 240px' }}
              />
              <button
                type="submit"
                className="btn btn--sm"
                disabled={zipBusy || !pluginUrl.trim()}
              >
                {t('skills.pluginPreview')}
              </button>
            </form>
            <p className="field__hint" style={{ marginTop: 12, marginBottom: 6 }}>
              {t('skills.zipSummary')}
            </p>
            <input
              type="file"
              accept=".zip,.nouspack,.nousplugin"
              onChange={(e) =>
                void handleZipSelected(e.target.files?.[0] ?? null)
              }
            />
            {zipBusy && (
              <p className="muted" style={{ fontSize: 13 }}>
                {t('skills.zipBusy')}
              </p>
            )}
            {zipPreview && (
              <div style={{ marginTop: 12 }}>
                <p style={{ margin: '0 0 8px', fontSize: 14 }}>
                  <strong>{zipPreview.name}</strong>{' '}
                  <span className="mono faint">
                    {zipPreview.pack_id}@{zipPreview.version}
                  </span>{' '}
                  <span className="badge badge--draft">{zipPreview.format}</span>
                </p>
                <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
                  {zipPreview.description}
                </p>
                <p style={{ fontSize: 13, marginBottom: 6 }}>
                  {t('skills.zipPermissions')}
                </p>
                <div className="pack-card__tags">
                  {zipPreview.permissions_requested.map((perm) => (
                    <label
                      key={perm}
                      className="keyword"
                      style={{ cursor: 'pointer' }}
                    >
                      <input
                        type="checkbox"
                        checked={zipGrants.includes(perm)}
                        onChange={() => toggleGrant(perm)}
                        style={{ marginRight: 6 }}
                      />
                      {perm}
                    </label>
                  ))}
                </div>
                <ul style={{ fontSize: 13, marginTop: 10 }}>
                  {zipPreview.skills.map((s) => (
                    <li key={s.key}>
                      {s.name}
                      {s.tools_local_exposed.length > 0 && (
                        <span className="mono faint">
                          {' '}
                          → {s.tools_local_exposed.join(', ')}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
                {zipPreview.warnings.length > 0 && (
                  <p className="muted" style={{ fontSize: 12 }}>
                    {t('skills.zipWarning', {
                      warnings: zipPreview.warnings.join('；'),
                    })}
                  </p>
                )}
                <div className="row" style={{ marginTop: 10 }}>
                  <button
                    type="button"
                    className="btn btn--sm btn--primary"
                    disabled={zipBusy || zipPreview.errors.length > 0}
                    onClick={() =>
                      void (pluginUrl.trim() && !zipFile
                        ? handleUrlInstall()
                        : handleImportZip())
                    }
                  >
                    {t('skills.zipInstall')}
                  </button>
                </div>
              </div>
            )}
          </div>

          {installedPacks.length > 0 && (
            <div className="card" style={{ marginTop: 14 }}>
              <h3 style={{ marginTop: 0, fontSize: 15 }}>
                {t('skills.installedTitle')}
              </h3>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
                {installedPacks.map((p) => (
                  <li key={p.id} style={{ marginBottom: 8 }}>
                    <strong>{p.name}</strong>{' '}
                    <span className="mono faint">
                      {p.pack_id}@{p.version}
                    </span>{' '}
                    {p.format ? (
                      <span className="badge badge--draft">{p.format}</span>
                    ) : null}{' '}
                    <span className={`badge badge--${p.status === 'active' ? 'active' : 'draft'}`}>
                      {p.status}
                    </span>
                    <span className="faint">
                      {' '}
                      · {p.skill_count} skills · {p.tool_count} tools
                    </span>
                    <div className="row" style={{ marginTop: 4 }}>
                      <button
                        type="button"
                        className="btn btn--sm"
                        onClick={() =>
                          void setInstalledPackStatus(
                            p.id,
                            p.status === 'active' ? 'disabled' : 'active',
                          ).then(async () => {
                            await refreshInstalledPacks();
                            await load();
                          })
                        }
                      >
                        {p.status === 'active'
                          ? t('common.disable')
                          : t('common.enable')}
                      </button>
                      <button
                        type="button"
                        className="btn btn--sm btn--danger"
                        onClick={() => {
                          if (
                            !window.confirm(
                              t('skills.confirmUninstall', { name: p.name }),
                            )
                          )
                            return;
                          void uninstallPack(p.id).then(async () => {
                            setNotice(t('skills.uninstalled'));
                            await refreshInstalledPacks();
                            await load();
                          });
                        }}
                      >
                        {t('skills.uninstall')}
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <details className="card" style={{ marginTop: 14 }}>
            <summary style={{ cursor: 'pointer', fontWeight: 600 }}>
              {t('skills.jsonSummary')}
            </summary>
            <p className="field__hint" style={{ marginTop: 10 }}>
              {t('skills.jsonHint')}
            </p>
            <textarea
              rows={6}
              value={importJson}
              onChange={(e) => setImportJson(e.target.value)}
              placeholder='{"skills":[{"name":"示例","instruction":"...","trigger_keywords":["demo"]}]}'
              style={{ marginTop: 8 }}
            />
            <div className="row" style={{ marginTop: 10 }}>
              <button
                type="button"
                className="btn btn--sm btn--primary"
                disabled={!importJson.trim()}
                onClick={() => void handleImportJson()}
              >
                {t('skills.jsonImport')}
              </button>
            </div>
          </details>
        </section>

      <div className="card" style={{ marginBottom: 18 }}>
        <form className="row" onSubmit={handleProbe}>
          <input
            type="search"
            value={probeQuery}
            onChange={(e) => setProbeQuery(e.target.value)}
            placeholder={t('skills.probePlaceholder')}
            aria-label={t('skills.probeAria')}
          />
          <button
            type="submit"
            className="btn btn--icon"
            disabled={probing || !probeQuery.trim()}
            aria-label={probing ? t('skills.probing') : t('skills.probe')}
            title={probing ? t('skills.probing') : t('skills.probe')}
          >
            {probing ? (
              <span className="spinner" aria-hidden="true" />
            ) : (
              <FlaskMark />
            )}
          </button>
        </form>

        {probeResults !== null && (
          <div style={{ marginTop: 12 }}>
            {probeResults.length === 0 ? (
              <p className="muted" style={{ margin: 0, fontSize: 13 }}>
                {t('skills.probeEmpty')}
              </p>
            ) : (
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
                {probeResults.map((r) => (
                  <li key={r.id} style={{ marginBottom: 4 }}>
                    <strong>{r.name}</strong>{' '}
                    <span className="mono faint">
                    {t('skills.probeScore', {
                      score: r.score,
                      vector: r.vector_similarity,
                      keyword: r.keyword_score,
                    })}
                    </span>
                    {r.matched_keywords.length > 0 && (
                      <span className="mono muted">
                        {' '}
                      {t('skills.probeHits', {
                        hits: r.matched_keywords.join(', '),
                      })}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      <div className="filters">
        <input
          type="search"
          value={search}
          placeholder={t('skills.searchPlaceholder')}
          aria-label={t('skills.searchAria')}
          onChange={(e) => {
            setSearch(e.target.value);
            setOffset(0);
          }}
        />
        <select
          value={statusFilter}
          aria-label={t('skills.filterAria')}
          onChange={(e) => {
            setStatusFilter(e.target.value as SkillStatus | '');
            setOffset(0);
          }}
        >
          <option value="">{t('skills.allStatuses')}</option>
          <option value="active">{t('status.active')}</option>
          <option value="draft">{t('status.draft')}</option>
          <option value="disabled">{t('status.disabled')}</option>
          <option value="deprecated">{t('status.deprecated')}</option>
        </select>
      </div>

      {loading ? (
        <div className="empty row" style={{ justifyContent: 'center' }}>
          <span className="spinner" aria-hidden="true" />
          <span>{t('common.loading')}</span>
        </div>
      ) : items.length === 0 ? (
        <div className="empty">
          {t('skills.empty')}
        </div>
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t('skills.colName')}</th>
                  <th>{t('skills.colStatus')}</th>
                  <th>{t('skills.colSource')}</th>
                  <th>{t('skills.colVersion')}</th>
                  <th>{t('skills.colUsage')}</th>
                  <th>{t('skills.colSuccess')}</th>
                  <th>{t('skills.colCreated')}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((skill) => (
                  <tr key={skill.id}>
                    <td>
                      <button
                        type="button"
                        onClick={() => navigate(`/skills/${skill.id}`)}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: 'var(--accent)',
                          padding: 0,
                          textAlign: 'left',
                        }}
                      >
                        {skill.name}
                      </button>
                      {skill.description && (
                        <div
                          className="faint"
                          style={{
                            fontSize: 12,
                            maxWidth: 340,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {skill.description}
                        </div>
                      )}
                    </td>
                    <td>
                      <span className={`badge badge--${skill.status}`}>
                        {t(STATUS_KEY[skill.status])}
                      </span>
                    </td>
                    <td className="faint">
                      {skill.source === 'auto'
                        ? t('source.auto')
                        : skill.source === 'imported'
                          ? t('source.imported')
                          : t('source.manual')}
                    </td>
                    <td className="mono">v{skill.version}</td>
                    <td className="mono">{skill.usage_count}</td>
                    <td className="mono">
                      {skill.success_rate === null ||
                      skill.success_rate === undefined
                        ? '—'
                        : `${Math.round(skill.success_rate * 100)}%`}
                    </td>
                    <td className="faint mono">
                      {formatDate(skill.created_at)}
                    </td>
                    <td>
                      <div className="table__actions">
                        <button
                          type="button"
                          className="btn btn--icon"
                          disabled={busyId === skill.id}
                          onClick={() => void toggleStatus(skill)}
                          aria-label={
                            skill.status === 'active'
                              ? t('common.disable')
                              : t('common.enable')
                          }
                          title={
                            skill.status === 'active'
                              ? t('common.disable')
                              : t('common.enable')
                          }
                        >
                          {skill.status === 'active' ? (
                            <PauseMark />
                          ) : (
                            <PlayMark />
                          )}
                        </button>
                        <button
                          type="button"
                          className="btn btn--icon"
                          disabled={busyId === skill.id}
                          onClick={() => void openEditor(skill.id)}
                          aria-label={t('common.edit')}
                          title={t('common.edit')}
                        >
                          <EditMark />
                        </button>
                        <button
                          type="button"
                          className="btn btn--icon btn--danger"
                          disabled={busyId === skill.id}
                          onClick={() => void handleDelete(skill)}
                          aria-label={t('common.delete')}
                          title={t('common.delete')}
                        >
                          <TrashMark />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="pagination">
            <span>
              {pageStart}–{pageEnd} / {total}
            </span>
            <div className="row">
              <button
                type="button"
                className="btn btn--sm"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              >
                {t('common.previous')}
              </button>
              <button
                type="button"
                className="btn btn--sm"
                disabled={pageEnd >= total}
                onClick={() => setOffset(offset + PAGE_SIZE)}
              >
                {t('common.next')}
              </button>
            </div>
          </div>
        </>
      )}

      <SkillEditor
        skill={editing}
        open={editorOpen}
        saving={saving}
        error={editorError}
        onClose={() => {
          setEditorOpen(false);
          setEditing(null);
        }}
        onSave={handleSave}
      />
    </div>
  );
}

function iconProps() {
  return {
    width: 16,
    height: 16,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2.15,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true as const,
  };
}

function FlaskMark() {
  return (
    <svg {...iconProps()}>
      <path d="M9.5 2h5" />
      <path d="M10 2v6.4L4.6 18.2A2.2 2.2 0 0 0 6.5 21.4h11a2.2 2.2 0 0 0 1.9-3.2L14 8.4V2" />
      <path d="M8.2 14.6h7.6" />
    </svg>
  );
}

function PlayMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="currentColor" d="M8.6 6.3v11.4L18.5 12Z" />
    </svg>
  );
}

function PauseMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <rect fill="currentColor" x="8" y="6.2" width="2.8" height="11.6" rx="0.8" />
      <rect fill="currentColor" x="13.2" y="6.2" width="2.8" height="11.6" rx="0.8" />
    </svg>
  );
}

function EditMark() {
  return (
    <svg {...iconProps()}>
      <path d="M12.4 20.2H20" />
      <path d="M16.2 4.6a2 2 0 0 1 2.8 2.8L8 18.4l-3.4.8.8-3.4Z" />
    </svg>
  );
}

function TrashMark() {
  return (
    <svg {...iconProps()}>
      <path d="M9.4 5.4c0-1 .8-1.8 1.8-1.8h1.6c1 0 1.8.8 1.8 1.8" />
      <path d="M5 7.4h14" />
      <path d="M7.3 7.4v10.1c0 1.2.9 2.1 2.1 2.1h5.2c1.2 0 2.1-.9 2.1-2.1V7.4" />
      <path d="M10 11.3v5M12 11.3v5M14 11.3v5" />
    </svg>
  );
}
