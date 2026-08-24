import { useMemo } from "react";
import { IHistoryProvider, HistoryProviderOptions } from "../HistoryProviders/IProvider";
import { NoneProvider } from "../HistoryProviders/None";
import { IndexedDBProvider } from "../HistoryProviders/IndexedDB";
import { CosmosDBProvider } from "../HistoryProviders/CosmosDB";

export const useHistoryManager = (provider: HistoryProviderOptions, ownerId?: string): IHistoryProvider => {
    const providerInstance = useMemo(() => {
        switch (provider) {
            case HistoryProviderOptions.IndexedDB:
                return ownerId ? new IndexedDBProvider("chat-database", "chat-history", ownerId) : new NoneProvider();
            case HistoryProviderOptions.CosmosDB:
                return new CosmosDBProvider();
            case HistoryProviderOptions.None:
            default:
                return new NoneProvider();
        }
    }, [provider, ownerId]);

    return providerInstance;
};
