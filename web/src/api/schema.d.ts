export interface paths {
    "/api/items/{item_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Item */
        get: operations["item_api_items__item_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Search */
        get: operations["search_api_search_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sources": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Sources */
        get: operations["sources_api_sources_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** BestUse */
        BestUse: {
            /** Item Id */
            item_id?: number | null;
            /** Name */
            name?: string | null;
            /** Profit Copper */
            profit_copper?: number | null;
            /** Reason */
            reason: string;
        };
        /** Evidence */
        Evidence: {
            /** Finished At */
            finished_at?: string | null;
            /** Freshness */
            freshness?: {
                [key: string]: unknown;
            } | null;
            /** Market Id */
            market_id: string;
            /** Scan Id */
            scan_id?: string | null;
            /** Source Id */
            source_id: string;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** Item */
        Item: {
            /** At Least */
            at_least: boolean;
            /** Crowding */
            crowding: string | null;
            /** Details */
            details: {
                [key: string]: unknown;
            };
            evidence: components["schemas"]["Evidence"];
            /** Held */
            held: number | null;
            /** Item Id */
            item_id: number;
            /** Listings */
            listings: number | null;
            made_from: components["schemas"]["BestUse"];
            /** Name */
            name: string;
            /** Overshoot */
            overshoot: string | null;
            /** Price Copper */
            price_copper: number | null;
            /** Quality */
            quality: number | null;
            /** Typical Copper */
            typical_copper: number | null;
            /** Units */
            units: number | null;
            used_in: components["schemas"]["BestUse"];
            /** Vendor Buy */
            vendor_buy: number[];
            /** Vendor Sell */
            vendor_sell: number | null;
        };
        /** SearchHit */
        SearchHit: {
            /** Item Id */
            item_id?: number | null;
            /** Kind */
            kind: string;
            /** Name */
            name: string;
            /** Quality */
            quality?: number | null;
            /** Variant Id */
            variant_id?: string | null;
            /** Variant State */
            variant_state?: string | null;
        };
        /** SourceOption */
        SourceOption: {
            /** Game Version */
            game_version: string;
            /** Label */
            label: string;
            /** Source Id */
            source_id: string;
        };
        /** Sources */
        Sources: {
            evidence: components["schemas"]["Evidence"] | null;
            /** Questions */
            questions: {
                [key: string]: string;
            };
            selected: components["schemas"]["SourceOption"] | null;
            /** Sources */
            sources: components["schemas"]["SourceOption"][];
            /** Waiting */
            waiting: number | null;
            /** Waiting Error */
            waiting_error?: string | null;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    item_api_items__item_id__get: {
        parameters: {
            query?: {
                source?: string;
            };
            header?: never;
            path: {
                item_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Item"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    search_api_search_get: {
        parameters: {
            query?: {
                source?: string;
                q?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SearchHit"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    sources_api_sources_get: {
        parameters: {
            query?: {
                source?: string;
                inventory?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Sources"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
