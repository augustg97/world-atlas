# Card text: which Wikipedia article belongs to which card

Written by `Research/modeling/audit_cardtext.py`. The page shows, on a location card, the lead of one English Wikipedia
article, fetched from en.wikipedia.org when the card opens; `web/data/wiki.json` names the article and
`build/wiki_titles.py` chose it. No Wikipedia text is in the repository.

Titles last checked against en.wikipedia.org: 2026-11-12.

## Coverage

| kind | cards | with an article | without | how the article was found |
|---|---|---|---|---|
| city | 7342 | 7094 (96.6%) | 248 | Natural Earth's id 7069, name search, place-checked 20, GeoNames id 5 |
| country | 247 | 247 (100.0%) | 0 | Natural Earth's id 247 |
| dispute | 27 | 22 (81.5%) | 5 | Natural Earth's id 22 |
| feature | 640 | 593 (92.7%) | 47 | Natural Earth's id 573, name search, place-checked 20 |
| peak | 81 | 68 (84.0%) | 13 | Natural Earth's id 62, name search, place-checked 6 |
| river | 449 | 400 (89.1%) | 49 | Natural Earth's id 393, name search, place-checked 7 |
| volcano | 1609 | 1116 (69.4%) | 493 | Smithsonian volcano number 1116 |
| all | 10395 | 9540 (91.8%) | 855 | |

A card with no article says so in one line and is otherwise complete. Rivers are counted by drawn reach: 462 reaches, of which
12 have no name and one has no line, leave 449 that can open a card.

## The place check

The mapped Wikidata item's own coordinate (P625) must lie within a limit of the card's position:

- **city**: 20 km + 0.012 km x sqrt(population): 20 km for a village, 58 km for a city of ten million
- **country**: inside the unit, or within half the diagonal of the box round all its parts (at least 100 km) of a point of its outline
- **dispute**: inside the area, or within half the diagonal of the box round all its parts (at least 100 km) of a point of its outline
- **feature**: 2.5 x the side of a square of the feature's drawn area (at least 150 km) from its label point
- **peak**: 30 km
- **river**: the drawn length of the reaches of that name (at least 60 km) from the nearest drawn point of any of them: a river's coordinate is its mouth or its source
- **volcano**: 30 km

A mapping further off than its limit is kept only if the article's title is the card's own name, accents and case aside, AND it lies
within 3 limits. For a feature the wider limit is 1000 km where its own is less, and no more: Natural Earth draws only a piece of
some seas, straits and reefs, and it also draws two ranges under one name. For a state it is at least 1000 km: the Seychelles are drawn
as one island. Where the item has no coordinate of its own (most rivers) the coordinates the English article carries stand in.
An article the build found by NAME (no id led to it) is held tighter: within 350 km, or under the card's own name within the limit.
A big thing's limit is thousands of km and a namesake fits inside it: the Sahel of Tunisia inside the Sahel's.

| kind | checked | median distance / limit | 95th percentile | worst |
|---|---|---|---|---|
| city | 7094 | 0.053 | 0.257 | 2.114 |
| country | 247 | 0.000 | 0.044 | 3.987 |
| dispute | 22 | 0.000 | 0.000 | 0.364 |
| feature | 593 | 0.076 | 0.390 | 6.241 |
| peak | 68 | 0.038 | 0.623 | 1.595 |
| river | 400 | 0.006 | 0.283 | 0.990 |
| volcano | 1116 | 0.017 | 0.282 | 2.559 |

Shipped mappings that fail the rule: **0**. Kept past the limit by name: 43. Checked by the article's coordinates: 795.
Unchecked (no coordinate or no title record): **0**.
Disambiguation pages: **0**. Titles that do not exist: **0**. Redirects (followed by the page): 42.
Keys that open no card: **0**. Articles shared by two cards of a kind: 36.

## Natural Earth ids the build refused

185 of Natural Earth's `wikidataid` values did not pass (the item is somewhere else, has no English article, has no
coordinate to check, or its article is a disambiguation page). Each was then tried by the other routes; the last column is what the card has now.

| kind | card | why refused | article now |
|---|---|---|---|
| city | Bose | Q92381: the item's coordinate lies 2821 km away (limit 25 km) | none |
| city | Tanjung Pandan | Q3056359: the item has no English article | Tanjungpandan (by name) |
| city | Jianmen | Q71323: the item's coordinate lies 100 km away (limit 36 km) | none |
| city | Jining | Q11060772: the item has no English article | none |
| city | Martapura | Q2358819: the item has no English article | Martapura, South Kalimantan (by name) |
| city | Alagoinhas | Q818261: the item has no English article | Alagoinhas (by name) |
| city | Darkhan | Q235571: the item's coordinate lies 34 km away (limit 23 km) | none |
| city | Bamian | Q214495: the item's coordinate lies 27 km away (limit 23 km) | none |
| city | El Kharga | Q4063326: the item has no English article | none |
| city | Kotabumi | Q10372500: the item has no English article | Kotabumi (by name) |
| city | Altai | Q433861: the item's coordinate lies 32 km away (limit 22 km) | none |
| city | As Sulayyil | Q27221: the item has no English article | none |
| city | Jyekundo | Q1558594: the item's coordinate lies 26 km away (limit 22 km) | none |
| city | Züünkharaa | Q1028289: the article's coordinate lies 42 km away (limit 22 km) | none |
| city | Derby | Q1018373: the item's coordinate lies 35 km away (limit 21 km) | none |
| city | Oktyabrsky | Q1691320: the item has no English article | none |
| city | Fulin | Q10954379: the item has no English article | none |
| city | Wyndham | Q477835: the item's coordinate lies 28 km away (limit 20 km) | none |
| city | Yerema | Q4176237: the item has no English article | none |
| city | Quilpie | Q985751: the item's coordinate lies 29 km away (limit 20 km) | none |
| city | Sayhut al Ghamirah | Q12217525: the item has no English article | none |
| city | Vorontsovo | Q2325752: the item has no English article | none |
| city | Matočkin Šar | Q3851905: the item has no English article | none |
| city | Indiga | Q3798263: the item has no English article | none |
| city | Gyda | Q1976289: the item has no English article | none |
| city | Nord | Q475535: the item's coordinate lies 22 km away (limit 20 km) | none |
| city | Djado | Q11856188: the item has no English article | Djado (by name) |
| city | Cilacap | Q12478970: the item has no English article | none |
| city | Letpadan | Q6533488: the item's coordinate lies 729 km away (limit 25 km) | Letpadan (by name) |
| city | Ninh Bình | Q33929: the item has no English article | Hoa Lư (city) (by name) |
| city | Longjiang | Q1869551: the item has no English article | none |
| city | Cuauhtémoc | Q2656480: the item's coordinate lies 38 km away (limit 24 km) | none |
| city | Wangqing | Q13897219: the item has no English article | none |
| city | Porto Santana | Q2105236: the item has no English article | none |
| city | Uvinza | Q133448: the item has no English article | none |
| city | Tailai | Q11145142: the item has no English article | none |
| city | Tamazunchale | Q2471832: the item has no English article | none |
| city | Lanxi | Q10893722: the item has no English article | none |
| city | Keshan | Q1522472: the item has no English article | none |
| city | Mocuba | Q520687: the item's coordinate lies 136 km away (limit 23 km) | none |
| city | Liuhe | Q11109923: the item has no English article | none |
| city | Pyongsan | Q18808: the item's coordinate lies 94 km away (limit 23 km) | none |
| city | Rafha | Q27219: the item has no English article | Rafha (by name) |
| city | Gannan | Q1493582: the item has no English article | none |
| city | Altagracia de Orituco | Q433758: the item has no English article | none |
| city | Santa Rita | Q976847: the item has no English article | none |
| city | San Fernando | Q745811: the item has no English article | none |
| city | Thung Song | Q15199303: the item has no English article | none |
| city | Kakonko | Q13123200: the item has no English article | none |
| city | Pochutla | Q602726: the item has no English article | none |
| city | Papasquiaro | Q2465593: the item's coordinate lies 25 km away (limit 22 km) | none |
| city | Oytal | Q3783220: the item's coordinate lies 286 km away (limit 22 km) | none |
| city | Yitulihe | Q10884943: the item has no English article | none |
| city | Anxi | Q4778099: the article's coordinate lies 167 km away (limit 22 km) | none |
| city | Pimentel | Q19950488: the item has no English article | none |
| city | Scottsdale | Q49221: the item's coordinate lies 23 km away (limit 21 km) | none |
| city | Chaguaramas | Q1058829: the item has no English article | Chaguaramas, Venezuela (by name) |
| city | Tamuín | Q2655761: the item has no English article | none |
| city | Ascension | Q2450325: the item's coordinate lies 7076 km away (limit 21 km) | none |
| city | Isla Mujeres | Q927815: the item's coordinate lies 30 km away (limit 21 km) | none |
| city | Aldama | Q3851217: the item has no English article | none |
| city | Santiago | Q27194740: the item has no English article | none |
| city | Puerto Quijarro | Q2117434: the item's coordinate lies 136 km away (limit 21 km) | none |
| city | Makale | Q57079173: the item has no English article | none |
| city | Komsomolets | Q1752218: the item has no English article | none |
| city | Olmos | Q27194541: the item has no English article | none |
| city | Villa Ahumada | Q20148488: the item has no English article | none |
| city | Kachiry | Q75251: the item's coordinate lies 25 km away (limit 21 km) | none |
| city | Marrupa | Q5649378: the item has no English article | none |
| city | Bayghanin | Q2115182: the item's coordinate lies 166 km away (limit 21 km) | none |
| city | Timiryazevskiy | Q4457440: the item has no English article | none |
| city | Tobol | Q1047817: the item has no English article | none |
| city | Rosario | Q540185: the item's coordinate lies 7485 km away (limit 21 km) | none |
| city | Ciudad Cortés | Q3925393: the item has no English article | none |
| city | Krasnogorsk | Q1786706: the item has no English article | none |
| city | Saranpaul | Q4408338: the item has no English article | none |
| city | Nyimba | Q3031656: the article's coordinate lies 33 km away (limit 20 km) | none |
| city | Tarutung | Q1883729: the item has no English article | Tarutung (by name) |
| city | Juina | Q1880608: the item's coordinate lies 83 km away (limit 20 km) | none |
| city | Mohembo | Q171089: the item has no English article | none |
| city | Zhaltyr | Q13640710: the item has no English article | none |
| city | Linxi | Q11106980: the item has no English article | none |
| city | Kaltukatjara | Q17976: the item's coordinate lies 102 km away (limit 20 km) | none |
| city | Kalima | Q1103496: the item's coordinate lies 22 km away (limit 20 km) | none |
| city | Halley Station | Q1571679: the item's coordinate lies 64 km away (limit 20 km) | none |
| city | Concordia Research Station | Q403127: the item's coordinate lies 54 km away (limit 20 km) | none |
| city | Lumbala Nguimbo | Q10320952: neither the item nor its article has a coordinate to check | none |
| city | Peregrebnoye | Q4350155: the item has no English article | none |
| city | Laryak | Q4254695: the item has no English article | none |
| city | Magta Lajar | Q2579658: the item's coordinate lies 71 km away (limit 20 km) | none |
| city | Il'pyrskiy | Q4199946: the item has no English article | none |
| city | Puerto Heath | Q6092075: the item has no English article | none |
| city | Hangu | Q1196666: the item's coordinate lies 54 km away (limit 27 km) | none |
| city | Escuintla | Q1477389: the item has no English article | none |
| city | Qal at Bishah | Q27135: the item has no English article | none |
| city | Três Lagoas | Q1637454: the item has no English article | Três Lagoas (by name) |
| city | Jaltipan | Q2447248: the item has no English article | none |
| city | Qinggang | Q8836938: the item has no English article | none |
| city | Suileng | Q13992688: the item has no English article | none |
| city | Alexandroupoli | Q190847: the item has no English article | none |
| city | Autlan | Q2589446: the item has no English article | none |
| city | San Lorenzo | Q549987: the item's coordinate lies 10481 km away (limit 23 km) | none |
| city | Orongen Zizhiqi | Q14230874: the item has no English article | none |
| city | Eldorado | Q1325690: the item's coordinate lies 22 km away (limit 22 km) | none |
| city | Piñas | Q7883868: the item has no English article | none |
| city | Amos | Q141705: the item has no English article | Amos, Quebec (by name) |
| city | Aqadyr | Q4056543: the item has no English article | none |
| city | Putina | Q3344150: the item's coordinate lies 78 km away (limit 21 km) | none |
| city | Bestobe | Q6352163: the item has no English article | none |
| city | Betanzos | Q671341: the item's coordinate lies 9102 km away (limit 21 km) | Betanzos, Bolivia (by name) |
| city | Esperanza | Q27940770: the item has no English article | none |
| city | Geraldton | Q3492487: the item's coordinate lies 23 km away (limit 20 km) | none |
| city | Villa Rumipal | Q10391476: the item has no English article | none |
| city | Cuya | Q5795129: the item has no English article | none |
| city | Omchak | Q14545882: the item has no English article | none |
| city | Pakhachi | Q4347325: the item has no English article | none |
| city | Chuquicamata | Q55342984: the item has no English article | none |
| city | Turgay | Q1956467: the item has no English article | none |
| city | El Progreso | Q686756: the item's coordinate lies 58 km away (limit 25 km) | none |
| city | Gramsh | Q18777: the item has no English article | none |
| city | An Nabk | Q6093787: the item has no English article | none |
| city | Machinga | Q12810684: the item's coordinate lies 33 km away (limit 20 km) | none |
| city | Dhuusa Mareeb | Q634063: the item's coordinate lies 26 km away (limit 20 km) | none |
| dispute | Kuril Is. | Q80389: the item's coordinate lies 302 km away (limit 179 km) | none |
| feature | Western Plateau | Q604846: neither the item nor its article has a coordinate to check | none |
| feature | Siwalik Hills | Q26813923: the item has no English article | none |
| feature | Manchurian Plain | Q28809720: the item has no English article | Northeast China Plain (by name) |
| feature | Sahel | Q23945221: the item has no English article | Sahel (by name) |
| feature | Bolshezemelskaya Tundra | Q2016601: neither the item nor its article has a coordinate to check | none |
| feature | Crystal Mountain | Q5191296: the item's coordinate lies 3851 km away (limit 1029 km) | none |
| feature | Ahag | Q23836082: the item has no English article | none |
| feature | Appennino Ligure | Q377264: the item has no English article | none |
| feature | Cordillera Oriental | Q143014: the item's coordinate lies 2119 km away (limit 1704 km) | none |
| feature | Cordillera Occidental | Q8463325: the item's coordinate lies 1787 km away (limit 848 km) | Cordillera Occidental (Colombia) (by name) |
| feature | Cordillera Blanca | Q804330: the article's coordinate lies 1293 km away (limit 937 km) | none |
| feature | Cordillera Oriental | Q4794486: the item's coordinate lies 1851 km away (limit 1387 km) | Cordillera Oriental (Colombia) (by name) |
| feature | Shan Plateau | Q27696359: the item has no English article | none |
| feature | Chaco Boreal | Q3820265: the item has no English article | Gran Chaco (by name) |
| feature | Chaco Austral | Q3775198: the item has no English article | none |
| feature | Yungas | Q743261: neither the item nor its article has a coordinate to check | none |
| feature | Queen Mary Coast | Q21471424: the item has no English article | none |
| feature | Adélie Coast | Q21489984: the item has no English article | none |
| feature | Wilhelm II Coast | Q21489993: the item has no English article | Kaiser Wilhelm II Land (by name) |
| feature | Ryukyu Islands | Q10905515: the item has no English article | none |
| feature | Falkland Islands | Q1249802: the item has no English article | Falkland Islands (by name) |
| feature | Bahama Islands | Q21713615: the item has no English article | Lucayan Archipelago (by name) |
| feature | Prince Edward Island | Q15120268: the item has no English article | none |
| feature | Lena Delta | Q2298744: the item has no English article | none |
| feature | Serra Geral | Q22041906: the item has no English article | Serra Geral (by name) |
| feature | Serra da Mantiquiera | Q22071997: the item has no English article | none |
| feature | Columbia Kootenay Mountain | Q22529966: the item has no English article | none |
| feature | Western Sayan | Q1974954: the item has no English article | none |
| feature | Hamada du Draa | Q20155858: the item has no English article | none |
| feature | Bié Plateau | Q776345: neither the item nor its article has a coordinate to check | none |
| feature | Loess Plateau | Q293730: neither the item nor its article has a coordinate to check | none |
| feature | Banadir | Q806070: the item's coordinate lies 569 km away (limit 467 km) | none |
| feature | Southern Cook Islands | Q11826289: the item has no English article | none |
| feature | Yangtze | Q5413: the item's coordinate lies 2840 km away (limit 167 km) | none |
| peak | Nganglong Mountains | Q4062402: the item has no English article | none |
| peak | Gora Manas | Q13171265: the item has no English article | none |
| peak | Shāh Fōlādī | Q20191405: the item has no English article | none |
| peak | Kuh-e Jang Qal'eh | Q20190966: the item has no English article | none |
| peak | Argun | Q24032213: the item has no English article | Argun (mountain) (by name) |
| peak | Nanda Devi | Q26794321: the item has no English article | Nanda Devi (by name) |
| peak | Daba Mountains | Q29613993: the item has no English article | none |
| river | Abay | the drawn reach holds more than one river of this name (Q3501984, Q882739) | none |
| river | Colorado | the drawn reach holds more than one river of this name (Q1265, Q270627) | none |
| river | Grande | the drawn reach holds more than one river of this name (Q1519602, Q386331) | none |
| river | Abay | the drawn reach holds more than one river of this name (Q3501984, Q882739) | none |
| river | Borcea | Q12722938: the item has no English article | none |
| river | Bénoué | Q204806: the item's coordinate lies 597 km away (limit 411 km) | none |
| river | Colorado | the drawn reach holds more than one river of this name (Q1265, Q270627) | none |
| river | Grande | the drawn reach holds more than one river of this name (Q1519602, Q386331) | none |
| river | Konqi | Q625404: neither the item nor its article has a coordinate to check | none |
| river | Koukourou | Q22555212: the item has no English article | none |
| river | Lom | Q23672111: the item has no English article | none |
| river | Lualaba | Q836812: the item's coordinate lies 1238 km away (limit 534 km) | none |
| river | Malyy Yenisey | Q1511505: the article's coordinate lies 158 km away (limit 107 km) | none |
| river | Negro | the drawn reach holds more than one river of this name (Q118771, Q817337) | none |
| river | Paraná | the drawn reach holds more than one river of this name (Q127892, Q21847787) | none |
| river | Pilcomayo | Q21806688: the item has no English article | none |
| river | Ruki | Q2635327: the article's coordinate lies 204 km away (limit 95 km) | Ruki River (by name) |
| river | San Juan | the drawn reach holds more than one river of this name (Q1161204, Q933176) | none |
| river | Soroksari Duna | Q1252126: the item has no English article | none |
| river | Verde | Q28457542: the article's coordinate lies 591 km away (limit 217 km) | none |

## Articles found without Natural Earth's id

By GeoNames id, or by name (exactly one item of that name says it is that kind of thing, has an English article and passes the place check).

| kind | card | route | article | km |
|---|---|---|---|---|
| city | Tanjung Pandan | name | Tanjungpandan | 1 |
| city | Martapura | name | Martapura, South Kalimantan | 2 |
| city | Alagoinhas | name | Alagoinhas | 1 |
| city | Nabire | geonames | Nabire | 2 |
| city | Kotabumi | name | Kotabumi | 2 |
| city | Djado | name | Djado | 1 |
| city | Majene | geonames | Majene | 2 |
| city | Letpadan | name | Letpadan | 1 |
| city | Ninh Bình | name | Hoa Lư (city) | 0 |
| city | Rafha | name | Rafha | 3 |
| city | Kampene | geonames | Kampene | 0 |
| city | Yandoon | name | Nyaungdon Township | 1 |
| city | Kualakapuas | geonames | Kuala Kapuas | 12 |
| city | Nzega | geonames | Nzega | 1 |
| city | Chaguaramas | name | Chaguaramas, Venezuela | 0 |
| city | Lubutu | name | Lubutu | 0 |
| city | Tarutung | name | Tarutung | 0 |
| city | Cazombo | name | Cazombo | 3 |
| city | Luiana | name | Luiana | 2 |
| city | Churchill Falls | name | Churchill Falls, Newfoundland and Labrador | 2 |
| city | Piso Firme | name | Piso Firme | 15 |
| city | Três Lagoas | name | Três Lagoas | 6 |
| city | Amos | name | Amos, Quebec | 0 |
| city | Betanzos | name | Betanzos, Bolivia | 1 |
| city | El Cayo | name | San Ignacio, Belize | 1 |
| feature | Manchurian Plain | name | Northeast China Plain | 41 |
| feature | Sahel | name | Sahel | 519 |
| feature | Mitumba Mountains | name | Mitumba Mountains | 512 |
| feature | Central Highlands | name | Central Highlands (Vietnam) | 69 |
| feature | Cordillera Occidental | name | Cordillera Occidental (Colombia) | 218 |
| feature | Cordillera Oriental | name | Cordillera Oriental (Colombia) | 16 |
| feature | Arnhem Land | name | Arnhem Land | 61 |
| feature | Chaco Boreal | name | Gran Chaco | 306 |
| feature | Wilhelm II Coast | name | Kaiser Wilhelm II Land | 244 |
| feature | Mergui Archipelago | name | Mergui Archipelago | 88 |
| feature | Falkland Islands | name | Falkland Islands | 44 |
| feature | Bahama Islands | name | Lucayan Archipelago | 162 |
| feature | Serra Geral | name | Serra Geral | 327 |
| feature | Abakan Range | name | Abakan Range | 239 |
| feature | Western Ghats | name | Western Ghats | 69 |
| feature | Gyda Peninsula | name | Gyda Peninsula | 137 |
| feature | Huíla Plateau | name | Huíla Plateau | 99 |
| feature | Kazakh Uplands | name | Kazakh Uplands | 75 |
| feature | Stanovoy Range | name | Stanovoy Range | 981 |
| feature | Virgin Islands | name | Virgin Islands | 41 |
| peak | Argun | name | Argun (mountain) | 1 |
| peak | Qattara Depression | name | Qattara Depression | 5 |
| peak | Amne Machin | name | Amne Machin | 0 |
| peak | Mount Taibai | name | Mount Taibai | 1 |
| peak | Nanda Devi | name | Nanda Devi | 19 |
| peak | Grandiozny Peak | name | Grandiozny Peak | 4 |
| river | La Grande Rivière | name | La Grande River | 8 |
| river | Mountain Nile | name | White Nile | 154 |
| river | Glåma | name | Glomma | 18 |
| river | La Grande Rivière | name | La Grande River | 8 |
| river | Mananantanana | name | Mananantanana | 9 |
| river | Ruki | name | Ruki River | 1 |
| river | Sungari | name | Songhua River | 8 |

## Cards without an article

### city (248)

By first reason (numbers and ids taken out):

- 117 x name:  other items carry the name,  say they are this kind of thing,  pass the place check
- 70 x ne:  the item has no English article
- 36 x ne:  the item's coordinate lies  km away (limit  km)
- 21 x geonames:  the item has no English article
- 3 x ne:  the article's coordinate lies  km away (limit  km)
- 1 x ne:  neither the item nor its article has a coordinate to check

The first 40:

- Jinxi: geonames: Q28809648: the item has no English article; name: 15 other items carry the name, 6 say they are this kind of thing, 0 pass the place check
- Bose: ne: Q92381: the item's coordinate lies 2821 km away (limit 25 km); name: 12 other items carry the name, 1 say they are this kind of thing, 0 pass the place check
- Santa Cruz: name: 19 other items carry the name, 9 say they are this kind of thing, 0 pass the place check
- Dulan: name: 4 other items carry the name, 3 say they are this kind of thing, 0 pass the place check
- Jianmen: ne: Q71323: the item's coordinate lies 100 km away (limit 36 km); name: 5 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Wanzhou: geonames: Q28795286: the item has no English article; name: 4 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Vila Velha: name: 8 other items carry the name, 3 say they are this kind of thing, 0 pass the place check
- Natal: name: 2 other items carry the name, 1 say they are this kind of thing, 0 pass the place check
- Yuci: geonames: Q28795640: the item has no English article; name: 8 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Jining: ne: Q11060772: the item has no English article; name: 7 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Crato: name: 4 other items carry the name, 2 say they are this kind of thing, 0 pass the place check
- Darkhan: ne: Q235571: the item's coordinate lies 34 km away (limit 23 km); name: 5 other items carry the name, 1 say they are this kind of thing, 0 pass the place check
- Bamian: ne: Q214495: the item's coordinate lies 27 km away (limit 23 km); name: 2 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- El Kharga: ne: Q4063326: the item has no English article; name: 1 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Altai: ne: Q433861: the item's coordinate lies 32 km away (limit 22 km); name: 15 other items carry the name, 2 say they are this kind of thing, 0 pass the place check
- As Sulayyil: ne: Q27221: the item has no English article; name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Jyekundo: ne: Q1558594: the item's coordinate lies 26 km away (limit 22 km); name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Züünkharaa: ne: Q1028289: the article's coordinate lies 42 km away (limit 22 km); name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Derby: ne: Q1018373: the item's coordinate lies 35 km away (limit 21 km); name: 19 other items carry the name, 8 say they are this kind of thing, 0 pass the place check
- Oktyabrsky: ne: Q1691320: the item has no English article; name: 29 other items carry the name, 29 say they are this kind of thing, 0 pass the place check
- Fulin: ne: Q10954379: the item has no English article; name: 14 other items carry the name, 2 say they are this kind of thing, 0 pass the place check
- Principe da Beira: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Govorovo: name: 5 other items carry the name, 3 say they are this kind of thing, 0 pass the place check
- Wyndham: ne: Q477835: the item's coordinate lies 28 km away (limit 20 km); name: 11 other items carry the name, 2 say they are this kind of thing, 0 pass the place check
- Yerema: ne: Q4176237: the item has no English article; name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Quilpie: ne: Q985751: the item's coordinate lies 29 km away (limit 20 km); name: 2 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Sayhut al Ghamirah: ne: Q12217525: the item has no English article; name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Lansdowne House: name: 12 other items carry the name, 1 say they are this kind of thing, 0 pass the place check
- Vorontsovo: ne: Q2325752: the item has no English article; name: 13 other items carry the name, 13 say they are this kind of thing, 0 pass the place check
- Matočkin Šar: ne: Q3851905: the item has no English article; name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Indiga: ne: Q3798263: the item has no English article; name: 2 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Gyda: ne: Q1976289: the item has no English article; name: 7 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Numto: name: 2 other items carry the name, 1 say they are this kind of thing, 0 pass the place check
- Komsa: name: 8 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Starorybnoye: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Mikhaylova: name: 9 other items carry the name, 6 say they are this kind of thing, 0 pass the place check
- Chagda: name: 3 other items carry the name, 1 say they are this kind of thing, 0 pass the place check
- Menkere: name: 1 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Sagastyr: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Khakhar: name: 2 other items carry the name, 0 say they are this kind of thing, 0 pass the place check

### dispute (5)

- Tirpani Valleys: no id
- Bara Hotii Valleys: no id
- Samdu Valleys: no id
- Lawa Headwaters: no id
- Kuril Is.: ne: Q80389: the item's coordinate lies 302 km away (limit 179 km)

### feature (47)

- Western Plateau: ne: Q604846: neither the item nor its article has a coordinate to check; name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Siwalik Hills: ne: Q26813923: the item has no English article; name: 1 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Central Lowlands: name: 4 other items carry the name, 3 say they are this kind of thing, 0 pass the place check
- Bolshezemelskaya Tundra: ne: Q2016601: neither the item nor its article has a coordinate to check; name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Selva: name: 16 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Crystal Mountain: ne: Q5191296: the item's coordinate lies 3851 km away (limit 1029 km); name: 23 other items carry the name, 14 say they are this kind of thing, 0 pass the place check
- Ahag: ne: Q23836082: the item has no English article; name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Eastern Sayan Mountains: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Hejaz Mountains: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Appennino Ligure: ne: Q377264: the item has no English article; name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Cordillera Oriental: ne: Q143014: the item's coordinate lies 2119 km away (limit 1704 km); name: 12 other items carry the name, 7 say they are this kind of thing, 0 pass the place check
- Cordillera Blanca: ne: Q804330: the article's coordinate lies 1293 km away (limit 937 km); name: 4 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Aldan Highlands: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Shan Plateau: ne: Q27696359: the item has no English article; name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Chaco Austral: ne: Q3775198: the item has no English article; name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Yungas: ne: Q743261: neither the item nor its article has a coordinate to check; name: 1 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Knud Ramussen Land: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Queen Mary Coast: ne: Q21471424: the item has no English article; name: 1 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Adélie Coast: ne: Q21489984: the item has no English article; name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Ryukyu Islands: ne: Q10905515: the item has no English article; name: 1 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Parry Islands: name: 5 other items carry the name, 2 say they are this kind of thing, 0 pass the place check
- Prince Edward Island: ne: Q15120268: the item has no English article; name: 5 other items carry the name, 2 say they are this kind of thing, 0 pass the place check
- Zambezi Delta: name: 1 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Lena Delta: ne: Q2298744: the item has no English article; name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Muchinga Mountains: name: 1 other items carry the name, 1 say they are this kind of thing, 0 pass the place check
- Serra da Mantiquiera: ne: Q22071997: the item has no English article; name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Columbia Kootenay Mountain: ne: Q22529966: the item has no English article; name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Western Sayan: ne: Q1974954: the item has no English article; name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Salt Range: name: 1 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Alataw Mountains: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Kuhrud Mountains: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Hamada du Draa: ne: Q20155858: the item has no English article; name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Tassili oua-n-Ahaggar: name: 2 other items carry the name, 2 say they are this kind of thing, 0 pass the place check
- Calanshio Sand Sea: name: 1 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Mosquito Coast: name: 6 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Iwembere Steppe: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Laurentides: name: 9 other items carry the name, 2 say they are this kind of thing, 2 pass the place check: Q2304022, Q75596
- Bié Plateau: ne: Q776345: neither the item nor its article has a coordinate to check; name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Grande Sertão Veredas National Park: name: 1 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Kimberley Plateau: name: 2 other items carry the name, 1 say they are this kind of thing, 0 pass the place check
- Loess Plateau: ne: Q293730: neither the item nor its article has a coordinate to check; name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Vychegda Lowland: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Banadir: ne: Q806070: the item's coordinate lies 569 km away (limit 467 km); name: 3 other items carry the name, 1 say they are this kind of thing, 0 pass the place check
- Entre Ríos: name: 11 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Tonga: name: 13 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Southern Cook Islands: ne: Q11826289: the item has no English article; name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Yangtze: ne: Q5413: the item's coordinate lies 2840 km away (limit 167 km); name: 2 other items carry the name, 0 say they are this kind of thing, 0 pass the place check

### peak (13)

- Cerro La Raya: name: 2 other items carry the name, 1 say they are this kind of thing, 0 pass the place check
- Nganglong Mountains: ne: Q4062402: the item has no English article; name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Gora Manas: ne: Q13171265: the item has no English article; name: 2 other items carry the name, 1 say they are this kind of thing, 0 pass the place check
- Shāh Fōlādī: ne: Q20191405: the item has no English article; name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Kuh-e Jang Qal'eh: ne: Q20190966: the item has no English article; name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Mönkh Saridag: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Gara Muleta: name: 4 other items carry the name, 1 say they are this kind of thing, 0 pass the place check
- Richat Structure: name: 2 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Talo: name: 8 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Gora Korolenko: name: 1 other items carry the name, 1 say they are this kind of thing, 0 pass the place check
- Daba Mountains: ne: Q29613993: the item has no English article; name: 1 other items carry the name, 1 say they are this kind of thing, 0 pass the place check
- Gora Burun-Shibertuy: name: 1 other items carry the name, 1 say they are this kind of thing, 0 pass the place check
- Golets Inyaptuk: name: 1 other items carry the name, 1 say they are this kind of thing, 0 pass the place check

### river (49)

- Abay: ne: the drawn reach holds more than one river of this name (Q3501984, Q882739)
- Colorado: ne: the drawn reach holds more than one river of this name (Q1265, Q270627)
- Grande: ne: the drawn reach holds more than one river of this name (Q1519602, Q386331)
- R. des Outaouais: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Svir’: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- São  Francisco: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Verkhniy Yenisey: name: 1 other items carry the name, 1 say they are this kind of thing, 0 pass the place check
- Abay: ne: the drawn reach holds more than one river of this name (Q3501984, Q882739)
- Amu  Darya: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Ergun: name: 3 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Borcea: ne: Q12722938: the item has no English article; name: 5 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Bratul Sfintu Gheorghe: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Bykovskaya Protoka: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Bénoué: ne: Q204806: the item's coordinate lies 597 km away (limit 411 km); name: 4 other items carry the name, 1 say they are this kind of thing, 0 pass the place check
- Colorado: ne: the drawn reach holds more than one river of this name (Q1265, Q270627)
- Damietta Branch: name: 1 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Zapadnaya Dvina: name: 2 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Ferenc Csatorna: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Genala: name: 1 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Grande: ne: the drawn reach holds more than one river of this name (Q1519602, Q386331)
- Ismailiya Canal: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Yangtze: name: 2 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Konqi: ne: Q625404: neither the item nor its article has a coordinate to check; name: 2 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Koukourou: ne: Q22555212: the item has no English article; name: 4 other items carry the name, 2 say they are this kind of thing, 0 pass the place check
- Lom: ne: Q23672111: the item has no English article; name: 8 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Lualaba: ne: Q836812: the item's coordinate lies 1238 km away (limit 534 km); name: 4 other items carry the name, 2 say they are this kind of thing, 0 pass the place check
- Congo: name: 13 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Malyy Yenisey: ne: Q1511505: the article's coordinate lies 158 km away (limit 107 km); name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Damqogkanbab: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- N. Fork Kuskokwim: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Negro: ne: the drawn reach holds more than one river of this name (Q118771, Q817337)
- Nmai: name: 1 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Olenekskaya Protoka: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Paraiba: name: 3 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Paraná: ne: the drawn reach holds more than one river of this name (Q127892, Q21847787)
- Pilcomayo: ne: Q21806688: the item has no English article; name: 4 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- R. des Outaouais: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Rosetta Branch: name: 2 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- San Juan: ne: the drawn reach holds more than one river of this name (Q1161204, Q933176)
- Selenge (Selenga): name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Shatt al Arab: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Soroksari Duna: ne: Q1252126: the item has no English article; name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Svir’: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- São  Francisco: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Trofimovskaya Protoka: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Tumatskaya Protoka: name: 0 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Verde: ne: Q28457542: the article's coordinate lies 591 km away (limit 217 km); name: 5 other items carry the name, 1 say they are this kind of thing, 0 pass the place check
- Brahmaputra: name: 2 other items carry the name, 0 say they are this kind of thing, 0 pass the place check
- Za: name: 1 other items carry the name, 0 say they are this kind of thing, 0 pass the place check

### volcano (493)

By first reason (numbers and ids taken out):

- 227 x gvp:  the item has no English article
- 183 x no number in the catalogue, or no item with it
- 45 x gvp:  items carry that id (Q, Q) and  pass
- 11 x gvp:  items carry that id (Q, Q, Q) and  pass
- 9 x gvp:  items carry that id (Q, Q, Q, Q) and  pass
- 9 x gvp:  the item's coordinate lies  km away (limit  km)
- 2 x gvp:  items carry that id (Q, Q, Q, Q, Q, Q) and  pass
- 2 x gvp:  neither the item nor its article has a coordinate to check
- 1 x gvp:  items carry that id (Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q, Q) and  pass
- 1 x gvp:  the article's coordinate lies  km away (limit  km)
- 1 x gvp:  items carry that id (Q, Q, Q, Q, Q) and  pass
- 1 x gvp:  items carry that id (Q, Q, Q, Q, Q, Q, Q, Q) and  pass

The first 40:

- West Eifel Volcanic Field: gvp: Q23925898: the item has no English article
- Chaine des Puys: gvp: 48 items carry that id (Q1068630, Q113111989, Q113622569, Q113623008, Q21532074, Q21532096, Q21532108, Q28493689, Q29422025, Q3114564, Q3114585, Q31393929, Q31394752, Q31394836, Q31394840, Q31394847, Q31394849, Q31394856, Q31394955, Q31394956, Q31394961, Q31394962, Q31394963, Q31669881, Q31669898, Q31669916, Q31682172, Q32161576, Q32161590, Q3229393, Q3273698, Q3411078, Q3411084, Q3411087, Q3411089, Q3411095, Q3411096, Q3411102, Q3411104, Q3411123, Q34804561, Q49064985, Q607372, Q92096639, Q97188481, Q97188487, Q97188494, Q97292947) and 5 pass
- Olot Volcanic Field: gvp: 6 items carry that id (Q1141050, Q11954938, Q1859850, Q3562714, Q3562719, Q6104324) and 3 pass
- Campi Flegrei: gvp: 3 items carry that id (Q1084616, Q3322000, Q755123) and 2 pass
- Vesuvius: gvp: 2 items carry that id (Q524, Q729873) and 2 pass
- Campi Flegrei del Mar di Sicilia: gvp: 4 items carry that id (Q1339167, Q2484387, Q3388772, Q833975) and 3 pass
- Santorini: gvp: 3 items carry that id (Q129296, Q2071883, Q2860219) and 2 pass
- Nisyros: gvp: Q2168190: the item has no English article
- Kars Plateau: no number in the catalogue, or no item with it
- Kazbek: gvp: 2 items carry that id (Q1828337, Q207680) and 2 pass
- Kabargin Oth Group: no number in the catalogue, or no item with it
- Unnamed: no number in the catalogue, or no item with it
- Samsari Volcanic Center: gvp: 3 items carry that id (Q23925903, Q2961734, Q3653186) and 2 pass
- Ghegham Volcanic Ridge: gvp: 4 items carry that id (Q1570517, Q16371120, Q2150879, Q2622594) and 2 pass
- Jalua: no number in the catalogue, or no item with it
- Alu-Dalafilla: gvp: 2 items carry that id (Q1607790, Q447277) and 2 pass
- Dalaffilla: no number in the catalogue, or no item with it
- Kurub: gvp: Q3200621: the item has no English article
- Gabillema: gvp: Q3093519: the item has no English article
- Kone: gvp: Q3198640: the item has no English article
- Boset: gvp: Q2911466: the item has no English article
- Bishoftu Volcanic Field: gvp: Q2904679: the item has no English article
- Gedemsa: gvp: Q3100052: the item has no English article
- Bora-Bericcio: gvp: Q2910587: the item has no English article
- Bora-Bericha-Tullu Moye: gvp: Q3541980: the item has no English article
- Butajiri-Silti Field: gvp: Q2928813: the item has no English article
- Aluto: gvp: Q125156: the item has no English article
- Chiracha: gvp: Q2963895: the item has no English article
- Tosa Sucha: no number in the catalogue, or no item with it
- Korath Range: gvp: Q3198899: the item has no English article
- Mega Volcanic Field: gvp: Q3041064: the item has no English article
- Segererua Plateau: gvp: Q13538916: the item has no English article
- Kilimanjaro: no number in the catalogue, or no item with it
- May-ya-moto: no number in the catalogue, or no item with it
- Nyamulagira: gvp: 2 items carry that id (Q695846, Q746568) and 2 pass
- Bufumbira: gvp: Q2927681: the item has no English article
- Cameroon: gvp: 2 items carry that id (Q190562, Q6651058) and 2 pass
- Manengouba: no number in the catalogue, or no item with it
- Ngaoundere Plateau: no number in the catalogue, or no item with it
- Biu Plateau: no number in the catalogue, or no item with it

## Kept past the limit because the article's title is the card's name

- city 'Shizuishan' -> Shizuishan: 42 km (limit 24 km)
- city 'Whyalla' -> Whyalla: 46 km (limit 22 km)
- city 'Shaoyang' -> Shaoyang: 38 km (limit 23 km)
- city 'Bayankhongor' -> Bayankhongor: 24 km (limit 22 km)
- city 'Bir Lehlou' -> Bir Lehlou: 27 km (limit 20 km)
- city 'Androka' -> Androka: 39 km (limit 20 km)
- city 'Patiala' -> Patiala: 36 km (limit 27 km)
- city 'Biak' -> Biak: 27 km (limit 24 km)
- city 'Koidu' -> Koidu: 26 km (limit 24 km)
- city 'Koktokay' -> Koktokay: 35 km (limit 23 km)
- city 'Kogalym' -> Kogalym: 25 km (limit 23 km)
- city 'Lisburn' -> Lisburn: 41 km (limit 21 km)
- city 'Kalabo' -> Kalabo: 29 km (limit 21 km)
- city 'Calulo' -> Calulo: 29 km (limit 20 km)
- city 'Las Plumas' -> Las Plumas: 33 km (limit 20 km)
- city 'Davis Station' -> Davis Station: 23 km (limit 20 km)
- city 'Neumayer Station III' -> Neumayer Station III: 29 km (limit 20 km)
- city 'Sierra Mojada' -> Sierra Mojada: 41 km (limit 20 km)
- city 'Uruará' -> Uruará: 35 km (limit 20 km)
- city 'Newcastle Waters' -> Newcastle Waters: 22 km (limit 20 km)
- city 'Hathras' -> Hathras: 27 km (limit 24 km)
- city 'Nauta' -> Nauta: 23 km (limit 21 km)
- city 'Bærum' -> Bærum: 46 km (limit 24 km)
- city 'Forecariah' -> Forécariah: 33 km (limit 21 km)
- country 'British Indian Ocean Territory' -> British Indian Ocean Territory: 169 km (limit 100 km)
- country 'Pitcairn Islands' -> Pitcairn Islands: 194 km (limit 100 km)
- country 'Seychelles' -> Seychelles: 399 km (limit 100 km)
- country 'Tuvalu' -> Tuvalu: 172 km (limit 100 km)
- feature 'Canadian Shield' -> Canadian Shield: 766 km (limit 150 km)
- feature 'Luzon Strait' -> Luzon Strait: 229 km (limit 150 km)
- feature 'Scotia Sea' -> Scotia Sea: 936 km (limit 150 km)
- feature 'Drake Passage' -> Drake Passage: 666 km (limit 150 km)
- feature 'Great Barrier Reef' -> Great Barrier Reef: 740 km (limit 150 km)
- peak 'Mount Batu' -> Mount Batu: 48 km (limit 30 km)
- volcano 'Boomerang Seamount' -> Boomerang Seamount: 72 km (limit 30 km)
- volcano 'Kerguelen Islands' -> Kerguelen Islands: 45 km (limit 30 km)
- volcano 'Lopevi' -> Lopevi: 40 km (limit 30 km)
- volcano 'Bliznets' -> Bliznets: 77 km (limit 30 km)
- volcano 'Kebeney' -> Kebeney: 39 km (limit 30 km)
- volcano 'Voyampolsky' -> Voyampolsky: 36 km (limit 30 km)
- volcano 'Manda-Inakir' -> Manda-Inakir: 32 km (limit 30 km)
- volcano 'Atakor Volcanic Field' -> Atakor volcanic field: 31 km (limit 30 km)
- volcano 'Thordarhyrna' -> Thordarhyrna: 30 km (limit 30 km)

## One article on two cards

- city: Q8156 is the article of 2 cards: Bandar Lampung|105.268|-5.428; Bandar Lampung|105.300|-5.450
- city: Q11506 is the article of 2 cards: Denpasar|115.220|-8.650; Kuta|115.184|-8.715
- city: Q175323 is the article of 2 cards: Adapazarı|30.415|40.800; Sakarya|30.400|40.767
- city: Q198989 is the article of 2 cards: Aqtau|51.236|43.623; Mangyshlak|51.142|43.690
- city: Q852735 is the article of 2 cards: Kasserine|8.717|35.217; Qasserine|8.830|35.180
- feature: Q76034 is the article of 2 cards: Canadian Shield|Tundra|-100.930|57.240; Canadian Shield|Tundra|-75.000|45.630
- feature: Q319671 is the article of 2 cards: Transantarctic Mountains|Range/mtn|-73.230|-84.760; Transantarctic Mountains|Range/mtn|159.280|-78.940
- feature: Q214284 is the article of 2 cards: Stanovoy Range|Plateau|111.810|56.870; Stanovoy Range|Range/mtn|130.140|55.600
- feature: Q208347 is the article of 2 cards: Chaco Boreal|Plain|-60.250|-21.660; Gran Chaco|Plain|-60.830|-24.570
- feature: Q118899 is the article of 2 cards: Brazilian Highlands|Plateau|-45.230|-15.520; Brazilian Highlands|Plateau|-47.150|-13.130
- feature: Q1796029 is the article of 2 cards: Queen Maud Mountains|Range/mtn|-161.250|-85.870; Queen Maud Mountains|Range/mtn|174.850|-85.430
- feature: Q4527 is the article of 2 cards: Western Ghats|Range/mtn|74.390|15.810; Western Ghats|Range/mtn|77.130|9.550
- feature: Q81591 is the article of 2 cards: Great Rift Valley|Valley|30.320|-6.300; Great Rift Valley|Valley|36.910|5.050
- feature: Q208807 is the article of 2 cards: Guiana Highlands|Plateau|-58.310|2.690; Guiana Highlands|Range/mtn|-63.080|5.450
- feature: Q97 is the article of 2 cards: Atlantic Ocean|ocean|-16.480|-30.260; Atlantic Ocean|ocean|-28.840|34.230
- feature: Q98 is the article of 2 cards: Pacific Ocean|ocean|-125.750|-29.060; Pacific Ocean|ocean|-147.390|29.190
- feature: Q7343 is the article of 2 cards: Great Barrier Reef|reef|142.890|-10.380; Great Barrier Reef|reef|146.360|-17.000
- river: Q34589 is the article of 3 cards: Al Furat; Euphrates; Firat
- river: Q4814791 is the article of 4 cards: Albert Nile; Mountain Nile; Victoria Nile; White Nile
- river: Q40855 is the article of 2 cards: Dnepre; Dnieper
- river: Q128102 is the article of 2 cards: Ertis; Irtysh
- river: Q7355 is the article of 2 cards: Huang; Yellow
- river: Q584 is the article of 2 cards: Rhein; Rhine
- river: Q1511505 is the article of 2 cards: Kyzyl-Khem; Shishhid Gol
- river: Q14294 is the article of 2 cards: Tagus; Tajo
- river: Q26076 is the article of 2 cards: Ayeyarwady; Irrawaddy Delta
- river: Q135477 is the article of 2 cards: Bamingui; Chari
- river: Q45403 is the article of 2 cards: Brahmaputra; Dihang
- river: Q2635327 is the article of 2 cards: Busira; Tshuapa
- river: Q171840 is the article of 2 cards: Caquetá; Japurá
- river: Q188773 is the article of 2 cards: Cubango; Okavango
- river: Q35591 is the article of 2 cards: Dicle; Tigris
- river: Q26422 is the article of 2 cards: Nu; Salween
- river: Q179444 is the article of 2 cards: Potomac; S. Branch Potomac
- river: Q134350 is the article of 2 cards: Tisa; Tisza
- river: Q78707 is the article of 2 cards: Verkhniy Yenisey; Yenisey

## HIGH findings

None.
