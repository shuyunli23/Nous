const TAG = /\[(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?\]/g;

function stampToSeconds(min, sec, frac) {
  let extra = 0;
  if (frac) {
    extra = frac.length === 1 ? Number(frac) / 10 : frac.length === 2 ? Number(frac) / 100 : Number(frac) / 1000;
  }
  return Number(min) * 60 + Number(sec) + extra;
}

function formatStamp(seconds) {
  const t = Math.max(0, seconds);
  const min = Math.floor(t / 60);
  let cs = Math.round((t - min * 60) * 100);
  let sec = Math.floor(cs / 100);
  cs %= 100;
  if (sec >= 60) {
    sec -= 60;
    return formatStamp((min + 1) * 60 + sec + cs / 100);
  }
  return `[${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}.${String(cs).padStart(2, '0')}]`;
}

export function looksLikeLrc(text) {
  if (!text) return false;
  return (text.match(/\[\d{1,2}:\d{2}/g) || []).length >= 2;
}

export function shiftLrc(text, deltaSeconds) {
  if (!text || !deltaSeconds) return text;
  return text.replace(TAG, (_full, min, sec, frac) => {
    return formatStamp(stampToSeconds(min, sec, frac) + deltaSeconds);
  });
}

export function parseLrc(text) {
  if (!text) return [];
  const lines = [];
  for (const raw of text.split(/\r?\n/)) {
    const tags = [...raw.matchAll(TAG)];
    if (!tags.length) continue;
    const content = raw.replace(/\[[^\]]*\]/g, '').trim();
    if (!content) continue;
    for (const match of tags) {
      lines.push({
        time: stampToSeconds(match[1], match[2], match[3]),
        text: content,
      });
    }
  }
  lines.sort((a, b) => a.time - b.time);
  return lines;
}

export function activeLineIndex(lines, currentTime) {
  if (!lines.length) return -1;
  let index = 0;
  for (let i = 0; i < lines.length; i += 1) {
    if (lines[i].time <= currentTime + 0.08) index = i;
    else break;
  }
  return index;
}
