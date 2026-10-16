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
    "/api/items/{item_id}/activity": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Activity */
        get: operations["activity_api_items__item_id__activity_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/items/{item_id}/chain": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Chain */
        get: operations["chain_api_items__item_id__chain_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/items/{item_id}/history": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** History */
        get: operations["history_api_items__item_id__history_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/items/{item_id}/ladder": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Ladder */
        get: operations["ladder_api_items__item_id__ladder_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/market": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Market */
        get: operations["market_api_market_get"];
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
    "/api/team": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Team */
        get: operations["team_api_team_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/team/character": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Character */
        get: operations["character_api_team_character_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/team/hire/{profession}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Hire */
        get: operations["hire_api_team_hire__profession__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/today/plan": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Plan */
        post: operations["plan_api_today_plan_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/today/settings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Settings */
        post: operations["settings_api_today_settings_post"];
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
        /** Activity */
        Activity: {
            /** At Least */
            at_least: boolean;
            /** Captures */
            captures: {
                [key: string]: unknown;
            }[];
            /** Farming */
            farming: {
                [key: string]: unknown;
            }[];
            /** Held */
            held: number | null;
            /** Holdings */
            holdings: {
                [key: string]: unknown;
            }[];
            /** Holdings Warning */
            holdings_warning: string | null;
            /** Sales Error */
            sales_error: string | null;
            /** Unidentified Sales */
            unidentified_sales: number;
            /** Wowhead Url */
            wowhead_url: string;
            /** Your Sales */
            your_sales: {
                [key: string]: unknown;
            }[];
        };
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
        /** Card */
        Card: {
            /** Faction */
            faction: string;
            /** Gold Copper */
            gold_copper: number | null;
            /** History */
            history: {
                [key: string]: unknown;
            }[];
            /** Last Seen Relative */
            last_seen_relative: string;
            /** Last Seen Utc */
            last_seen_utc: string;
            /** Level */
            level: number | null;
            /** Machine */
            machine: string | null;
            /** Name */
            name: string;
            /** Professions */
            professions: components["schemas"]["Skill"][];
            /** Realm */
            realm: string;
            /** Skills Status */
            skills_status: string;
            /** Stale */
            stale: boolean;
        } & {
            [key: string]: unknown;
        };
        /** Chain */
        Chain: {
            /** Demand */
            demand: {
                [key: string]: unknown;
            }[];
            /** In Chain */
            in_chain: boolean;
            /** Made From */
            made_from: {
                [key: string]: unknown;
            }[];
            /** Used In */
            used_in: {
                [key: string]: unknown;
            }[];
        };
        /** CharacterRecord */
        CharacterRecord: {
            card: components["schemas"]["Card"];
            /** Character */
            character: [
                string,
                string,
                string
            ];
            /** Evidence */
            evidence: {
                [key: string]: unknown;
            };
            holdings: components["schemas"]["Holdings"];
            progression: components["schemas"]["Progression"];
        };
        /** Comparison */
        Comparison: {
            /** Character */
            character: [
                string,
                string,
                string
            ];
            /** Professions */
            professions: components["schemas"]["ComparisonProfession"][];
        };
        /** ComparisonBest */
        ComparisonBest: {
            /** Name */
            name: string;
            /** Profit Copper */
            profit_copper: number | null;
        } & {
            [key: string]: unknown;
        };
        /** ComparisonProfession */
        ComparisonProfession: {
            best: components["schemas"]["ComparisonBest"] | null;
            /** Profession */
            profession: string;
        };
        /** Estimate */
        Estimate: {
            /** Complete */
            complete: boolean;
            /** Cost Copper */
            cost_copper?: number | null;
            /**
             * Reasons
             * @default []
             */
            reasons: string[];
            /**
             * Steps
             * @default []
             */
            steps: {
                [key: string]: unknown;
            }[];
        } & {
            [key: string]: unknown;
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
        /** HireBest */
        HireBest: {
            /** Output Item Id */
            output_item_id: number;
            /** Output Name */
            output_name: string;
            /** Profit Copper */
            profit_copper: number | null;
        } & {
            [key: string]: unknown;
        };
        /** HireDetail */
        HireDetail: {
            /** Needs Pattern */
            needs_pattern: number;
            /** Profession */
            profession: string;
            /** Tiers */
            tiers: {
                [key: string]: unknown;
            }[];
            /** Unknown Source */
            unknown_source: number;
        } & {
            [key: string]: unknown;
        };
        /** HireRow */
        HireRow: {
            best: components["schemas"]["HireBest"] | null;
            estimate: components["schemas"]["Estimate"];
            /** Holders */
            holders: components["schemas"]["Holder"][];
            /** Profession */
            profession: string;
        };
        /** History */
        History: {
            /** Note */
            note: string;
            /** Other Identities */
            other_identities: number;
            /** Points */
            points: components["schemas"]["HistoryPoint"][];
            /** Removals */
            removals: {
                [key: string]: unknown;
            };
            /** Removals Error */
            removals_error: string | null;
            /** Scans */
            scans: {
                [key: string]: unknown;
            }[];
        };
        /** HistoryPoint */
        HistoryPoint: {
            /** Finished At */
            finished_at: string;
            /** Metrics */
            metrics: {
                [key: string]: unknown;
            } | null;
            /** Scan Id */
            scan_id: string;
        };
        /** Holder */
        Holder: {
            /** Character */
            character: [
                string,
                string,
                string
            ];
            /** Max Rank */
            max_rank: number | null;
            /** Rank */
            rank: number | null;
        };
        /** Holdings */
        Holdings: {
            /** Captures */
            captures: {
                [key: string]: unknown;
            }[];
            /** Items */
            items: {
                [key: string]: unknown;
            }[];
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
        /** Ladder */
        Ladder: {
            /** Freshness */
            freshness: {
                [key: string]: unknown;
            };
            /** No Buyout Listings */
            no_buyout_listings: number;
            /** No Buyout Units */
            no_buyout_units: number;
            /** Note */
            note: string;
            /** Rows */
            rows: components["schemas"]["LadderRow"][];
            /** Scan */
            scan: {
                [key: string]: unknown;
            };
            /** Zoom Copper */
            zoom_copper: number | null;
        };
        /** LadderRow */
        LadderRow: {
            /** Cumulative Units */
            cumulative_units: number;
            /** Listings */
            listings: number;
            /** Price Copper */
            price_copper: number;
            /** Units */
            units: number;
        };
        /** Market */
        Market: {
            /** Chain Count */
            chain_count: number;
            evidence: components["schemas"]["Evidence"];
            /** Floods */
            floods: {
                [key: string]: unknown;
            };
            /** Movement */
            movement: {
                [key: string]: unknown;
            };
            /** Note */
            note: string;
            /** Pulse */
            pulse: {
                [key: string]: {
                    [key: string]: unknown;
                }[];
            };
            /** Removals */
            removals: {
                [key: string]: unknown;
            };
            /** Rows */
            rows: components["schemas"]["MarketRow"][];
            /** Warning */
            warning: string | null;
        };
        /** MarketRow */
        MarketRow: {
            /** Gap Copper */
            gap_copper: number | null;
            /** Gap Percent */
            gap_percent: number | null;
            /** Item Id */
            item_id: number;
            /** Listings */
            listings: number | null;
            /** Name */
            name: string;
            /** Price Copper */
            price_copper: number | null;
            /** Quality */
            quality: number | null;
            /** Roles */
            roles: string[];
            /** Signal */
            signal: {
                [key: string]: unknown;
            } | null;
            /** Sparkline */
            sparkline: (number | null)[];
            /** Typical Copper */
            typical_copper: number | null;
            /** Units */
            units: number | null;
            /** Variant Id */
            variant_id: string | null;
            /** Variant State */
            variant_state: string | null;
        };
        /** Member */
        Member: {
            card: components["schemas"]["Card"];
            /** Character */
            character: [
                string,
                string,
                string
            ];
            progression: components["schemas"]["Progression"];
        };
        /** Payback */
        Payback: {
            /** Crafts */
            crafts: number | null;
            /**
             * Status
             * @enum {string}
             */
            status: "absent" | "unknown" | "never" | "crafts";
        };
        /** PlanRequest */
        PlanRequest: {
            /** State */
            state?: {
                [key: string]: unknown;
            };
            /**
             * View
             * @default route
             * @enum {string}
             */
            view: "route" | "opportunities" | "level-up";
        };
        /** Profession */
        Profession: {
            alternative: components["schemas"]["Recipe"] | null;
            /** Alternative Kind */
            alternative_kind: ("learn" | "hunt") | null;
            best: components["schemas"]["Recipe"] | null;
            /** Gathering */
            gathering: boolean;
            /** Max Rank */
            max_rank: number | null;
            /**
             * Next Step
             * @enum {string}
             */
            next_step: "note" | "best" | "none";
            /** Note */
            note: string;
            /** Profession */
            profession: string;
            /** Rank */
            rank: number | null;
            /** Recipes */
            recipes: components["schemas"]["Recipe"][];
        } & {
            [key: string]: unknown;
        };
        /** Progression */
        Progression: {
            /** Professions */
            professions: components["schemas"]["Profession"][];
        } & {
            [key: string]: unknown;
        };
        /** Recipe */
        Recipe: {
            estimate: components["schemas"]["Estimate"];
            /** Learn From */
            learn_from: string;
            /** Name */
            name: string;
            /** Output Item Id */
            output_item_id: number;
            payback: components["schemas"]["Payback"];
            /** Points Needed */
            points_needed: number;
            /** Profit Copper */
            profit_copper: number | null;
            /** Required Skill */
            required_skill: number | null;
            /** Training Cost Copper */
            training_cost_copper?: number | null;
        } & {
            [key: string]: unknown;
        };
        /** RouteLine */
        RouteLine: {
            /** Evidence */
            evidence: {
                [key: string]: unknown;
            };
            /** Index */
            index: number;
            /** Text */
            text: string;
            /**
             * Warnings
             * @default
             */
            warnings: string;
        };
        /** RouteStop */
        RouteStop: {
            /** Character */
            character: string;
            /** Characters */
            characters: [
                string,
                string,
                string
            ][];
            /** Lines */
            lines: components["schemas"]["RouteLine"][];
            /** Place */
            place: string;
            /** Stage */
            stage: string;
        };
        /** SearchHit */
        SearchHit: {
            /** Character */
            character?: [
                string,
                string,
                string
            ] | null;
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
        /** SettingsRequest */
        SettingsRequest: {
            /** Settings */
            settings: {
                [key: string]: unknown;
            };
        };
        /** Skill */
        Skill: {
            /** At Cap */
            at_cap: boolean;
            /** Known Count */
            known_count: number | null;
            /** Max Rank */
            max_rank: number | null;
            /** Name */
            name: string;
            /** Possibly Incomplete */
            possibly_incomplete: boolean | null;
            /** Rank */
            rank: number | null;
            /** Recipe Source */
            recipe_source: string;
            /** Recipes At */
            recipes_at: string;
            /** Seen At */
            seen_at: string | null;
        } & {
            [key: string]: unknown;
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
        /** Team */
        Team: {
            /** All Incomplete */
            all_incomplete: boolean;
            /** Comparisons */
            comparisons: components["schemas"]["Comparison"][];
            evidence: components["schemas"]["Evidence"];
            /** Hires */
            hires: components["schemas"]["HireRow"][];
            /** Hiring Labels */
            hiring_labels: string;
            /** Labels */
            labels: string;
            /** No Catalog */
            no_catalog: string[];
            /** Notes */
            notes: string[];
            /** Roster */
            roster: components["schemas"]["Member"][];
        };
        /** TodayPlan */
        TodayPlan: {
            /** Characters */
            characters: string[][];
            /** Copy Text */
            copy_text: string;
            /**
             * Empty Reason
             * @default
             */
            empty_reason: string;
            /** Evidence */
            evidence?: {
                [key: string]: unknown;
            };
            /** Funds Copper */
            funds_copper: number;
            /** Funds Label */
            funds_label: string;
            /** Notes */
            notes: string[];
            /** Plan */
            plan: {
                [key: string]: unknown;
            };
            /** Reset Note */
            reset_note: string;
            /** Session */
            session?: {
                [key: string]: unknown;
            } | null;
            /** Settings */
            settings: {
                [key: string]: unknown;
            };
            /** State */
            state: {
                [key: string]: unknown;
            };
            /** Stops */
            stops: components["schemas"]["RouteStop"][];
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
                variant?: string;
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
    activity_api_items__item_id__activity_get: {
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
                    "application/json": components["schemas"]["Activity"];
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
    chain_api_items__item_id__chain_get: {
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
                    "application/json": components["schemas"]["Chain"];
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
    history_api_items__item_id__history_get: {
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
                    "application/json": components["schemas"]["History"];
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
    ladder_api_items__item_id__ladder_get: {
        parameters: {
            query?: {
                source?: string;
                scan?: string;
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
                    "application/json": components["schemas"]["Ladder"];
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
    market_api_market_get: {
        parameters: {
            query?: {
                source?: string;
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
                    "application/json": components["schemas"]["Market"];
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
    team_api_team_get: {
        parameters: {
            query?: {
                source?: string;
                window?: number;
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
                    "application/json": components["schemas"]["Team"];
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
    character_api_team_character_get: {
        parameters: {
            query: {
                name: string;
                realm: string;
                faction: string;
                source?: string;
                window?: number;
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
                    "application/json": components["schemas"]["CharacterRecord"];
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
    hire_api_team_hire__profession__get: {
        parameters: {
            query?: {
                source?: string;
            };
            header?: never;
            path: {
                profession: string;
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
                    "application/json": components["schemas"]["HireDetail"];
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
    plan_api_today_plan_post: {
        parameters: {
            query?: {
                source?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PlanRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TodayPlan"];
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
    settings_api_today_settings_post: {
        parameters: {
            query?: {
                source?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SettingsRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
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
