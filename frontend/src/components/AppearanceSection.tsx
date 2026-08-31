import { useAppearance } from '../appearance/AppearanceProvider';
import {
  CJK_FONTS,
  CJK_FONT_KEY,
  FONT_GROUP_KEY,
  FONT_GROUP_ORDER,
  LATIN_FONTS,
  LATIN_FONT_KEY,
  type FontOption,
} from '../appearance/fonts';
import {
  EFFECT_IDS,
  EFFECT_NAME_KEY,
  PERIODS,
  PERIOD_HOURS_KEY,
  PERIOD_KEY,
  type EffectId,
  type Period,
  type Surface,
} from '../appearance/types';
import { useI18n, type MessageKey } from '../i18n';
import WorkspaceSection from './WorkspaceSection';

function groupedOptions<Id extends string>(fonts: readonly FontOption<Id>[]) {
  return FONT_GROUP_ORDER.map((group) => ({
    group,
    items: fonts.filter((font) => font.group === group),
  })).filter((entry) => entry.items.length > 0);
}

function FontSelect<Id extends string>({
  label,
  value,
  fonts,
  nameKey,
  onChange,
}: {
  label: string;
  value: Id;
  fonts: readonly FontOption<Id>[];
  nameKey: Record<Id, MessageKey>;
  onChange: (id: Id) => void;
}) {
  const { t } = useI18n();
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value as Id)}>
        {groupedOptions(fonts).map(({ group, items }) => (
          <optgroup key={group} label={t(FONT_GROUP_KEY[group])}>
            {items.map((font) => (
              <option key={font.id} value={font.id}>
                {t(nameKey[font.id])}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </label>
  );
}

function EffectSelect({
  value,
  onChange,
  label,
}: {
  value: EffectId;
  onChange: (id: EffectId) => void;
  label: string;
}) {
  const { t } = useI18n();
  return (
    <label className="field">
      <span>{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value as EffectId)}
      >
        {EFFECT_IDS.map((id) => (
          <option key={id} value={id}>
            {t(EFFECT_NAME_KEY[id])}
          </option>
        ))}
      </select>
    </label>
  );
}

export default function AppearanceSection() {
  const { t } = useI18n();
  const { prefs, period, setPrefs } = useAppearance();

  function setMode(mode: 'manual' | 'schedule') {
    setPrefs({ ...prefs, mode });
  }

  function setManual(surface: Surface, id: EffectId) {
    setPrefs({
      ...prefs,
      manual: { ...prefs.manual, [surface]: id },
    });
  }

  function setSchedule(slot: Period, surface: Surface, id: EffectId) {
    setPrefs({
      ...prefs,
      schedule: {
        ...prefs.schedule,
        [slot]: { ...prefs.schedule[slot], [surface]: id },
      },
    });
  }

  return (
    <section id="appearance" className="section">
      <h2 className="section__title">{t('appearance.title')}</h2>
      <div className="card">
        <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
          {t('appearance.lead')}
        </p>

        <div className="seg" role="radiogroup" aria-label={t('appearance.mode')}>
          <button
            type="button"
            role="radio"
            aria-checked={prefs.mode === 'manual'}
            className={prefs.mode === 'manual' ? 'seg__btn seg__btn--on' : 'seg__btn'}
            onClick={() => setMode('manual')}
          >
            {t('appearance.modeManual')}
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={prefs.mode === 'schedule'}
            className={
              prefs.mode === 'schedule' ? 'seg__btn seg__btn--on' : 'seg__btn'
            }
            onClick={() => setMode('schedule')}
          >
            {t('appearance.modeSchedule')}
          </button>
        </div>

        {prefs.mode === 'manual' ? (
          <div className="appearance-grid">
            <EffectSelect
              label={t('appearance.graph')}
              value={prefs.manual.graph}
              onChange={(id) => setManual('graph', id)}
            />
            <EffectSelect
              label={t('appearance.sidebar')}
              value={prefs.manual.sidebar}
              onChange={(id) => setManual('sidebar', id)}
            />
          </div>
        ) : (
          <>
            <p className="appearance-now">
              {t('appearance.now', { period: t(PERIOD_KEY[period]) })}
            </p>
            <div className="appearance-table-wrap">
              <table className="appearance-table">
                <thead>
                  <tr>
                    <th>{t('appearance.slot')}</th>
                    <th>{t('appearance.graph')}</th>
                    <th>{t('appearance.sidebar')}</th>
                  </tr>
                </thead>
                <tbody>
                  {PERIODS.map((slot) => (
                    <tr
                      key={slot}
                      className={slot === period ? 'appearance-table__row--now' : ''}
                    >
                      <th>
                        {t(PERIOD_KEY[slot])}
                        <span>{t(PERIOD_HOURS_KEY[slot])}</span>
                      </th>
                      <td>
                        <select
                          value={prefs.schedule[slot].graph}
                          onChange={(event) =>
                            setSchedule(slot, 'graph', event.target.value as EffectId)
                          }
                          aria-label={`${t(PERIOD_KEY[slot])} ${t('appearance.graph')}`}
                        >
                          {EFFECT_IDS.map((id) => (
                            <option key={id} value={id}>
                              {t(EFFECT_NAME_KEY[id])}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        <select
                          value={prefs.schedule[slot].sidebar}
                          onChange={(event) =>
                            setSchedule(
                              slot,
                              'sidebar',
                              event.target.value as EffectId,
                            )
                          }
                          aria-label={`${t(PERIOD_KEY[slot])} ${t('appearance.sidebar')}`}
                        >
                          {EFFECT_IDS.map((id) => (
                            <option key={id} value={id}>
                              {t(EFFECT_NAME_KEY[id])}
                            </option>
                          ))}
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      <WorkspaceSection />

      <div className="card" style={{ marginTop: 12 }}>
        <h3 className="mode-card__name">{t('appearance.fontsTitle')}</h3>
        <p className="muted" style={{ marginTop: 6, fontSize: 13 }}>
          {t('appearance.fontsLead')}
        </p>
        <div className="font-picks">
          <FontSelect
            label={t('appearance.fontCjk')}
            value={prefs.cjkFont}
            fonts={CJK_FONTS}
            nameKey={CJK_FONT_KEY}
            onChange={(id) => setPrefs({ ...prefs, cjkFont: id })}
          />
          <FontSelect
            label={t('appearance.fontLatin')}
            value={prefs.latinFont}
            fonts={LATIN_FONTS}
            nameKey={LATIN_FONT_KEY}
            onChange={(id) => setPrefs({ ...prefs, latinFont: id })}
          />
        </div>
        <div className="font-preview">
          <span className="font-preview__label">{t('appearance.fontPreviewLabel')}</span>
          <p className="font-preview__sample">
            <span>{t('appearance.fontPreviewCjk')}</span>
            <span>{t('appearance.fontPreviewLatin')}</span>
          </p>
        </div>
      </div>
    </section>
  );
}
