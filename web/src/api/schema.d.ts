export interface paths {
    "/api/chains": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Outputs */
        get: operations["outputs_api_chains_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/chains/route": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Route */
        get: operations["route_api_chains_route_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/data": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Data */
        get: operations["data_api_data_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/data/discard": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Discard */
        post: operations["discard_api_data_discard_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/data/import": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Collect */
        post: operations["collect_api_data_import_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/data/imported": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Imported */
        get: operations["imported_api_data_imported_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/data/review": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Review */
        post: operations["review_api_data_review_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/data/selection": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Selection */
        post: operations["selection_api_data_selection_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
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
    "/api/ledger": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Ledger */
        get: operations["ledger_api_ledger_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ledger/movements": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Movements */
        get: operations["movements_api_ledger_movements_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ledger/targets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Targets */
        post: operations["targets_api_ledger_targets_post"];
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
        /** Capture */
        Capture: {
            /** Age Hours */
            age_hours: number | null;
            /** Character */
            character: string;
            /** Empty */
            empty: boolean;
            /** Excluded */
            excluded: number;
            /** Kind */
            kind: string;
            /** Partial */
            partial: boolean;
            /** Unknown */
            unknown: boolean;
        } & {
            [key: string]: unknown;
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
        /** Category */
        Category: {
            /** Category */
            category: string;
            /** In Copper */
            in_copper: number;
            /** Out Copper */
            out_copper: number;
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
        /** CharacterStatus */
        CharacterStatus: {
            /** Character */
            character: [
                string,
                string,
                string
            ];
            /** Character Reason */
            character_reason: string;
            /** Craft Status */
            craft_status: string;
            /** Training Cost Copper */
            training_cost_copper: number | null;
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
        /** Data */
        Data: {
            /** Chips */
            chips: string[];
            /** Cli */
            cli?: string | null;
            /** Details */
            details: {
                [key: string]: string;
            };
            /** Provider */
            provider: string;
        };
        /** Day */
        Day: {
            /** Day */
            day: string;
            /** In Copper */
            in_copper: number;
            /** Out Copper */
            out_copper: number;
        };
        /** Discard */
        Discard: {
            /** Review Id */
            review_id?: string | null;
        };
        /** Edge */
        Edge: {
            /** Child */
            child: number;
            /** Parent */
            parent: number;
            /** Quantity */
            quantity: number;
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
        /** Gold */
        Gold: {
            /** Categories */
            categories: components["schemas"]["Category"][];
            /** Daily */
            daily: components["schemas"]["Day"][];
            /** Evidence */
            evidence: {
                [key: string]: unknown;
            };
            /** Movement Count */
            movement_count: number;
            pairs: components["schemas"]["Pairs"];
            /** Reconciliation */
            reconciliation: components["schemas"]["GoldPair"][];
            team: components["schemas"]["GoldTeam"];
            /** Totals */
            totals: components["schemas"]["GoldTotal"][];
        };
        /** GoldPair */
        GoldPair: {
            /** Actual Copper */
            actual_copper: number | null;
            /** Character */
            character: [
                string,
                string,
                string
            ];
            /** From Utc */
            from_utc: string;
            /** Reason */
            reason: string | null;
            /** Recorded Copper */
            recorded_copper: number | null;
            /** To Utc */
            to_utc: string;
            /** Unexplained Copper */
            unexplained_copper: number | null;
        };
        /** GoldTeam */
        GoldTeam: {
            /** In Copper */
            in_copper: number;
            /** Net Copper */
            net_copper: number;
            /** Out Copper */
            out_copper: number;
        };
        /** GoldTotal */
        GoldTotal: {
            /** Category */
            category: string;
            /** Character */
            character: [
                string,
                string,
                string
            ];
            /** Day */
            day: string;
            /** In Copper */
            in_copper: number;
            /** Out Copper */
            out_copper: number;
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
        /** Import */
        Import: {
            /** Review Id */
            review_id: string;
            /** Selected */
            selected: string[];
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
        /** ItemResidual */
        ItemResidual: {
            /** Actual Units */
            actual_units: number;
            /** Character */
            character: [
                string,
                string,
                string
            ];
            /** From Utc */
            from_utc: string;
            /** Item Id */
            item_id: number;
            /** Kind */
            kind: string;
            /** Possibly Incomplete */
            possibly_incomplete: boolean;
            /** Recorded Units */
            recorded_units: number;
            /** Residual Units */
            residual_units: number;
            /** To Utc */
            to_utc: string;
        };
        /** ItemTeam */
        ItemTeam: {
            /** In Units */
            in_units: number;
            /** Out Units */
            out_units: number;
        };
        /** ItemTotal */
        ItemTotal: {
            /** Category */
            category: string;
            /** Character */
            character: [
                string,
                string,
                string
            ];
            /** Day */
            day: string;
            /** In Units */
            in_units: number;
            /** Out Units */
            out_units: number;
        };
        /** Items */
        Items: {
            /** Evidence */
            evidence: {
                [key: string]: unknown;
            };
            /** Movement Count */
            movement_count: number;
            /** Pairs */
            pairs: components["schemas"]["Pairs"][];
            /** Reconciliation */
            reconciliation: components["schemas"]["ItemResidual"][];
            team: components["schemas"]["ItemTeam"];
            /** Totals */
            totals: components["schemas"]["ItemTotal"][];
            /** Transfers */
            transfers: components["schemas"]["Transfer"][];
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
        /** Leaf */
        Leaf: {
            /** Depth */
            depth: string;
            /** Item Id */
            item_id: number;
            /** Method */
            method: string;
            /** Name */
            name: string;
            /** Quantity */
            quantity: number;
            /** Total Cost Copper */
            total_cost_copper: number | null;
            /** Unit Cost Copper */
            unit_cost_copper: number | null;
        };
        /** Ledger */
        Ledger: {
            /** Errors */
            errors: {
                [key: string]: string;
            };
            /** Evidence */
            evidence: {
                [key: string]: string;
            };
            gold: components["schemas"]["Gold"] | null;
            items: components["schemas"]["Items"] | null;
            /** Names */
            names: {
                [key: string]: string;
            };
            stock: components["schemas"]["Stock"] | null;
        };
        /** Line */
        Line: {
            /** Amount Copper */
            amount_copper: number | null;
            /** End Copper */
            end_copper: number | null;
            /** Label */
            label: string;
            /** Quantity */
            quantity?: number | null;
            /** Start Copper */
            start_copper: number;
            /** Unit Cost Copper */
            unit_cost_copper?: number | null;
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
        /** Movement */
        Movement: {
            /** Entry Id */
            entry_id: string;
            /** Item Id */
            item_id?: number | null;
            /** Machine */
            machine: string | null;
            /** Name */
            name?: string | null;
            /** Utc */
            utc: string;
        } & {
            [key: string]: unknown;
        };
        /** Node */
        Node: {
            /** At Least */
            at_least: boolean;
            /** Characters */
            characters: components["schemas"]["CharacterStatus"][];
            /** Column */
            column: number;
            /** Forced */
            forced: boolean;
            /** Held */
            held: number | null;
            /** Item Id */
            item_id: number;
            /** Maker */
            maker: string;
            /** Method */
            method: string;
            /** Name */
            name: string;
            /** Options */
            options: components["schemas"]["Option"][];
            /** Quality */
            quality?: number | null;
            /** Route Note */
            route_note: string;
            /** Unit Cost Copper */
            unit_cost_copper: number | null;
            /** Units */
            units: number;
        };
        /** Option */
        Option: {
            /** Method */
            method: string;
            /** Unit Cost Copper */
            unit_cost_copper: number;
        };
        /** Output */
        Output: {
            /** Catalog Id */
            catalog_id: string;
            /** Item Id */
            item_id: number;
            /** Name */
            name: string;
            /** Profession */
            profession: string;
            /** Profit Copper */
            profit_copper: number | null;
            /** Recipe Id */
            recipe_id: number;
        };
        /** Outputs */
        Outputs: {
            /** Hit Count */
            hit_count: number;
            /** Hits */
            hits: components["schemas"]["Output"][];
            /** Ranked */
            ranked: components["schemas"]["Output"][];
        };
        /** Pairs */
        Pairs: {
            /**
             * Kind
             * @default bags
             */
            kind: string;
            /** Reconciled */
            reconciled: number;
            /** Total */
            total: number;
            /**
             * Unknown
             * @default 0
             */
            unknown: number;
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
        /** Review */
        Review: {
            /**
             * Hits
             * @default []
             */
            hits: string[];
            /**
             * Messages
             * @default []
             */
            messages: [
                string,
                string
            ][];
            review?: components["schemas"]["Selection"] | null;
            /** Review Id */
            review_id?: string | null;
            /**
             * Success
             * @default false
             */
            success: boolean;
        };
        /** Route */
        Route: {
            /** Batch */
            batch: number;
            /** Can Add */
            can_add: boolean;
            /** Catalog Id */
            catalog_id: string;
            /** Edges */
            edges: components["schemas"]["Edge"][];
            /** Evidence */
            evidence: {
                [key: string]: unknown;
            };
            /** Leaves */
            leaves: components["schemas"]["Leaf"][];
            /** Max Crafts */
            max_crafts: number;
            /** Name */
            name: string;
            /** Nodes */
            nodes: components["schemas"]["Node"][];
            /** Profit Copper */
            profit_copper: number | null;
            /** Reason */
            reason: string;
            /** Recipe Id */
            recipe_id: number;
            source_evidence: components["schemas"]["Evidence"];
            /** Spend Copper */
            spend_copper: number | null;
            /** Waterfall */
            waterfall: components["schemas"]["Line"][];
        };
        /** RouteLine */
        RouteLine: {
            /** Display */
            display?: {
                [key: string]: unknown;
            };
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
            /** Role */
            role?: string | null;
            /** Variant Id */
            variant_id?: string | null;
            /** Variant State */
            variant_state?: string | null;
        };
        /** Selection */
        Selection: {
            /** Can Import */
            can_import: boolean;
            /** Choices */
            choices: string[];
            /** Clear */
            clear: string[];
            /** Default */
            default: string[];
            /** File Status */
            file_status: string[];
            /** Has Records */
            has_records: boolean;
            /** Lines */
            lines: string[];
            /** New */
            new: boolean;
            /** Notes */
            notes: string[];
            /** Problems */
            problems: string[];
            /** Sections */
            sections: [
                string,
                {
                    [key: string]: unknown;
                }[]
            ][];
            /** Selected */
            selected: string[];
            /** Selection Differs */
            selection_differs: boolean;
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
            /** Short Label */
            short_label: string;
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
        /** Stock */
        Stock: {
            /** Buy Cost Copper */
            buy_cost_copper: number;
            /** Captures */
            captures: components["schemas"]["Capture"][];
            /** Entries */
            entries: components["schemas"]["Target"][];
            /** Evidence */
            evidence: {
                [key: string]: unknown;
            };
            /** Excluded Prices */
            excluded_prices: number;
            /** Holdings */
            holdings: {
                [key: string]: unknown;
            }[];
            /** Items Held */
            items_held: number;
            /** Items Short */
            items_short: number;
            /** Names */
            names: {
                [key: string]: string;
            };
            /** Rows */
            rows: components["schemas"]["StockRow"][];
            /** Scan State */
            scan_state: string;
            /** Value Copper */
            value_copper: number;
        };
        /** StockRow */
        StockRow: {
            /** Above Limit Cost Copper */
            above_limit_cost_copper?: number | null;
            /** At Most */
            at_most: boolean;
            /** Buy Cost Copper */
            buy_cost_copper?: number | null;
            /** Buy Units */
            buy_units?: number | null;
            entry: components["schemas"]["Target"] | null;
            /** Fill Cost Copper */
            fill_cost_copper?: number | null;
            /** Fill State */
            fill_state: string;
            /** Held */
            held: number;
            /** Item Id */
            item_id: number;
            /** Limit Copper */
            limit_copper?: number | null;
            /** Limit Kind */
            limit_kind: string;
            /**
             * Limit Unknown
             * @default false
             */
            limit_unknown: boolean;
            /** Name */
            name: string;
            /** Purchased Units */
            purchased_units?: number | null;
            /** Short */
            short?: number | null;
            /** Target Units */
            target_units: number | null;
            /** Unlisted Units */
            unlisted_units?: number | null;
            /** Value Copper */
            value_copper: number | null;
            /** Variant Id */
            variant_id: string | null;
            /** Variant State */
            variant_state: string;
            /** Wait Cost Copper */
            wait_cost_copper?: number | null;
            /** Wait Units */
            wait_units?: number | null;
            /** Whole Stack Units */
            whole_stack_units?: number | null;
        };
        /** Target */
        Target: {
            /** Buy Copper */
            buy_copper?: number | null;
            /** Buy Percent */
            buy_percent?: number | null;
            /** Item Id */
            item_id: number;
            /** Target Units */
            target_units: number;
        };
        /** Targets */
        Targets: {
            /** Entries */
            entries: components["schemas"]["Target"][];
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
            characters: [
                string,
                string,
                string
            ][];
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
        /** Transfer */
        Transfer: {
            /** Item Id */
            item_id: number;
            /** Recipient */
            recipient: [
                string,
                string,
                string
            ];
            /** Sender */
            sender: [
                string,
                string,
                string
            ];
            /** Status */
            status: string;
            /** Units */
            units: number;
        } & {
            [key: string]: unknown;
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
    outputs_api_chains_get: {
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
                    "application/json": components["schemas"]["Outputs"];
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
    route_api_chains_route_get: {
        parameters: {
            query: {
                catalog_id: string;
                recipe_id: number;
                source?: string;
                batch?: number;
                force?: string[] | null;
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
                    "application/json": components["schemas"]["Route"];
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
    data_api_data_get: {
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
                    "application/json": components["schemas"]["Data"];
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
    discard_api_data_discard_post: {
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
                "application/json": components["schemas"]["Discard"];
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
                        [key: string]: boolean;
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
    collect_api_data_import_post: {
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
                "application/json": components["schemas"]["Import"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Review"];
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
    imported_api_data_imported_get: {
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
                    "application/json": [
                        string,
                        {
                            [key: string]: unknown;
                        }[]
                    ][];
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
    review_api_data_review_post: {
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
                    "application/json": components["schemas"]["Review"];
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
    selection_api_data_selection_post: {
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
                "application/json": components["schemas"]["Import"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Selection"];
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
    ledger_api_ledger_get: {
        parameters: {
            query?: {
                source?: string;
                days?: "7" | "30" | "all";
                q?: string;
                chains?: boolean;
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
                    "application/json": components["schemas"]["Ledger"];
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
    movements_api_ledger_movements_get: {
        parameters: {
            query: {
                name: string;
                realm: string;
                faction: string;
                day: string;
                category: string;
                ledger: "gold" | "items";
                source?: string;
                q?: string;
                chains?: boolean;
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
                    "application/json": components["schemas"]["Movement"][];
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
    targets_api_ledger_targets_post: {
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
                "application/json": components["schemas"]["Targets"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Targets"];
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
