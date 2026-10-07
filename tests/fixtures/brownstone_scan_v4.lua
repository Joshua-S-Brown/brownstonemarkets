BrownstoneScanDB = {
	["addon_version"] = "0.4.0",
	["schema_version"] = 4,
	["scans"] = {
		{
			["schema_version"] = 4,
			["scan_id"] = "enriched",
			["started_at"] = 1793816390,
			["finished_at"] = 1793816400,
			["finished_at_utc"] = "2026-11-04T18:20:00Z",
			["status"] = "completed",
			["listing_count"] = 5,
			["reported_count"] = 5,
			["api"] = "modern",
			["faction"] = {
				["player"] = "Alliance",
				["neutral_source"] = "undetermined",
			},
			["house"] = {
				["npc_name"] = "Example Auctioneer",
				["zone"] = "Stormwind City",
			},
			["listings"] = {
				"6538:1:500:0:0:1:1:1:4:2:10:1:1",
				"6538:2:300:0:0:1:2:2:1:2:10:1:2",
				"6538:1:1:0:0:1:0:0::::0:0",
				"2589:20:701:0:0:1:3:1:3:1:0:1:3",
				"2589:10:0:0:0:1:3:1:2:1:15:2:3",
			},
			["listing_format"] = "item_id:quantity:buyout:min_bid:bid:flags:name_index:seller_index:time_left:quality:level:level_type_index:link_index",
			["names"] = {
				"Willow Robe of the Monkey",
				"Willow Robe of the Bear",
				"Linen Cloth",
			},
			["sellers"] = {
				"TestSeller",
				"TestSeller-Other",
			},
			["level_types"] = {
				"REQ_LEVEL",
				"ITEM_LEVEL",
			},
			["links"] = {
				"|cnIQ2:|Hitem:6538::::::::1:1491:::1:12721::::::|h[Willow Robe of the Monkey]|h|r",
				"|cnIQ2:|Hitem:6538::::::::1:1491::1:1:12722:1:28:5240:::::|h[Willow Robe of the Bear]|h|r",
				"|cnIQ1:|Hitem:2589::::::::1:1491:::::::::|h[Linen Cloth]|h|r",
			},
			["duration_seconds"] = 12.5,
			["items"] = {
				{
					["item_id"] = 6538,
					["class_id"] = 4,
					["subclass_id"] = 1,
					["item_level"] = 15,
					["vendor_sell_copper"] = 0,
				},
				{
					["item_id"] = 2589,
				},
			},
			["item_pass"] = {
				["total"] = 2,
				["requested"] = 1,
				["received"] = 1,
				["failed"] = 0,
				["timed_out"] = 0,
				["cached"] = 1,
				["wait_limit_seconds"] = 20,
				["duration_seconds"] = 3.5,
				["status"] = "completed",
				["api"] = "C_Item.RequestLoadItemDataByID",
				["items"] = {
					{
						["item_id"] = 6538,
						["max_stack_size"] = 1,
					},
					{
						["item_id"] = 2589,
						["item_level"] = 5,
						["max_stack_size"] = 20,
						["vendor_sell_copper"] = 100,
					},
				},
			},
		},
	},
}
