function openDraftDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("yourspace-project-drafts", 1);
    request.onupgradeneeded = () => {
      const store = request.result.createObjectStore("drafts", { keyPath: ["ownerId", "id"] });
      store.createIndex("owner", "ownerId");
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function withDraftStore<T>(
  mode: IDBTransactionMode,
  operation: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  const database = await openDraftDatabase();
  try {
    return await new Promise((resolve, reject) => {
      const transaction = database.transaction("drafts", mode);
      const request = operation(transaction.objectStore("drafts"));
      transaction.oncomplete = () => resolve(request.result);
      transaction.onabort = () => reject(transaction.error);
    });
  } finally {
    database.close();
  }
}

export function readProjectDrafts<T>(ownerId: string): Promise<T[]> {
  return withDraftStore("readonly", (store) => store.index("owner").getAll(ownerId));
}

export function writeProjectDraft(draft: { ownerId: string; id: string }) {
  return withDraftStore("readwrite", (store) => store.put(draft));
}

export function deleteProjectDraft(ownerId: string, id: string) {
  return withDraftStore("readwrite", (store) => store.delete([ownerId, id]));
}
