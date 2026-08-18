import { IndexedDBProvider } from "../../components/HistoryProviders/IndexedDB";

export async function searchHistory(keyword: string) {
    const provider = new IndexedDBProvider("chat-database", "chat-history");
    const all = await provider.getAllItems();

    if (!all) return [];

    const lower = keyword.toLowerCase();

    return all.filter(item => item.question?.toLowerCase().includes(lower) || item.answer?.toLowerCase().includes(lower));
}
