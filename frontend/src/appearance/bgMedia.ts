const DB_NAME = 'nous-appearance';
const STORE = 'workspace-images';
const VERSION = 1;
export const MAX_BG_BYTES = 16 * 1024 * 1024;

export interface CustomBgMeta {
  id: string;
  name: string;
  mime: string;
  createdAt: number;
}

export interface CustomBgRecord extends CustomBgMeta {
  blob: Blob;
}

const ACCEPT_PREFIX = ['image/', 'video/mp4', 'video/webm'];

export function isAllowedBgFile(file: File): boolean {
  const mime = (file.type || '').toLowerCase();
  if (ACCEPT_PREFIX.some((p) => mime.startsWith(p) || mime === p)) return true;
  return /\.(gif|png|jpe?g|webp|avif|svg|mp4|webm)$/i.test(file.name);
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'id' });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error ?? new Error('indexedDB open failed'));
  });
}

function reqToPromise<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error ?? new Error('indexedDB request failed'));
  });
}

export async function saveCustomBg(file: File): Promise<CustomBgMeta> {
  if (!isAllowedBgFile(file)) {
    throw new Error('type');
  }
  if (file.size > MAX_BG_BYTES) {
    throw new Error('size');
  }
  const record: CustomBgRecord = {
    id: crypto.randomUUID(),
    name: file.name || 'background',
    mime: file.type || 'application/octet-stream',
    createdAt: Date.now(),
    blob: file,
  };
  const db = await openDb();
  try {
    await reqToPromise(db.transaction(STORE, 'readwrite').objectStore(STORE).put(record));
  } finally {
    db.close();
  }
  const { blob: _blob, ...meta } = record;
  return meta;
}

export async function getCustomBg(id: string): Promise<CustomBgRecord | null> {
  const db = await openDb();
  try {
    const row = await reqToPromise(
      db.transaction(STORE, 'readonly').objectStore(STORE).get(id),
    );
    return (row as CustomBgRecord | undefined) ?? null;
  } finally {
    db.close();
  }
}

export async function listCustomBgs(): Promise<CustomBgMeta[]> {
  const db = await openDb();
  try {
    const rows = (await reqToPromise(
      db.transaction(STORE, 'readonly').objectStore(STORE).getAll(),
    )) as CustomBgRecord[];
    return rows
      .map(({ id, name, mime, createdAt }) => ({ id, name, mime, createdAt }))
      .sort((a, b) => b.createdAt - a.createdAt);
  } finally {
    db.close();
  }
}

export async function deleteCustomBg(id: string): Promise<void> {
  const db = await openDb();
  try {
    await reqToPromise(db.transaction(STORE, 'readwrite').objectStore(STORE).delete(id));
  } finally {
    db.close();
  }
}

export function isVideoMime(mime: string): boolean {
  return mime.startsWith('video/');
}
