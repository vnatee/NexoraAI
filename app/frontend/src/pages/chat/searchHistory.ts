import { IndexedDBProvider } from "../../components/HistoryProviders/IndexedDB";

export async function searchHistory(keyword: string, ownerId: string) {
    const provider = new IndexedDBProvider("chat-database", "chat-history", ownerId);
    const all = await provider.getAllItems();

    if (!all) return [];

    const lower = keyword.toLowerCase();

    return all.filter(item => item.question?.toLowerCase().includes(lower) || item.answer?.toLowerCase().includes(lower));
}
