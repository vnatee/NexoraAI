import { IDBPDatabase, openDB } from "idb";
import { IHistoryProvider, Answers, HistoryProviderOptions, HistoryMetaData } from "./IProvider";

export class IndexedDBProvider implements IHistoryProvider {
    getProviderName = () => HistoryProviderOptions.IndexedDB;

    private dbName: string;
    private storeName: string;
    private ownerId: string;
    private dbPromise: Promise<IDBPDatabase> | null = null;
    private cursorKey: IDBValidKey | undefined;
    private isCusorEnd: boolean = false;

    constructor(dbName: string, storeName: string, ownerId: string) {
        this.dbName = dbName;
        this.storeName = storeName;
        this.ownerId = ownerId;
        this.cursorKey = undefined;
        this.isCusorEnd = false;
    }

    private async init() {
        const storeName = this.storeName;
        if (!this.dbPromise) {
            this.dbPromise = openDB(this.dbName, 1, {
                upgrade(db) {
                    if (!db.objectStoreNames.contains(storeName)) {
                        const store = db.createObjectStore(storeName, { keyPath: "id" });
                        store.createIndex("timestamp", "timestamp");
                    }
                }
            });
        }
        return this.dbPromise;
    }

    resetContinuationToken() {
        this.cursorKey = undefined;
        this.isCusorEnd = false;
    }

    async getNextItems(count: number): Promise<HistoryMetaData[]> {
        const db = await this.init();
        const tx = db.transaction(this.storeName, "readonly");
        const store = tx.objectStore(this.storeName);
        const index = store.index("timestamp");

        // return empty array if cursor is already at the end
        if (this.isCusorEnd) {
            return [];
        }

        // set cursor to the last key
        let cursor = this.cursorKey ? await index.openCursor(IDBKeyRange.upperBound(this.cursorKey), "prev") : await index.openCursor(null, "prev");

        // return empty array means no more history or no data. set isCursorEnd to true and return empty array
        if (!cursor) {
            this.isCusorEnd = true;
            return [];
        }

        const loadedItems: { id: string; title: string; timestamp: number; answers: Answers; ownerId: string }[] = [];
        while (loadedItems.length < count && cursor) {
            if (cursor.value?.ownerId === this.ownerId) {
                loadedItems.push(cursor.value);
            }
            cursor = await cursor.continue();
        }

        // set isCursorEnd to true if cursor is null
        if (!cursor) {
            this.isCusorEnd = true;
        }

        // update cursorKey
        this.cursorKey = cursor?.key;

        return loadedItems;
    }

    async addItem(id: string, answers: Answers): Promise<void> {
        if (!answers.length || !answers[answers.length - 1][0].trim()) {
            return;
        }

        const timestamp = new Date().getTime();
        const db = await this.init(); // 自動的に初期化
        const tx = db.transaction(this.storeName, "readwrite");
        const current = await tx.objectStore(this.storeName).get(id);
        if (current) {
            const title = answers.length ? answers[answers.length - 1][0] : current.title;
            if (current.ownerId !== this.ownerId) {
                throw new Error("Chat history item belongs to another user");
            }
            await tx.objectStore(this.storeName).put({ ...current, id, title, timestamp, answers, ownerId: this.ownerId });
        } else {
            // const title = answers[0][0].length > 50 ? answers[0][0].substring(0, 50) + "..." : answers[0][0];
            const title = answers.length ? answers[answers.length - 1][0] : "Untitled";
            await tx.objectStore(this.storeName).add({ id, title, timestamp, answers, ownerId: this.ownerId });
        }
        await tx.done;
        return;
    }

    async getItem(id: string): Promise<Answers | null> {
        const db = await this.init();
        const tx = db.transaction(this.storeName, "readonly");
        const item = await tx.objectStore(this.storeName).get(id);
        return item?.ownerId === this.ownerId ? item.answers : null;
    }

    async deleteItem(id: string): Promise<void> {
        const db = await this.init();
        const tx = db.transaction(this.storeName, "readwrite");
        const store = tx.objectStore(this.storeName);
        const item = await store.get(id);
        if (item?.ownerId === this.ownerId) {
            await store.delete(id);
        }
        await tx.done;
        return;
    }

    async getAllItems(): Promise<any[]> {
        const db = await this.init();
        const tx = db.transaction(this.storeName, "readonly");
        const store = tx.objectStore(this.storeName);

        const items = (await store.getAll()).filter(item => item?.ownerId === this.ownerId);
        await tx.done;
        return items;
    }
}
