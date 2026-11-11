# Lake ice against NSIDC G01377 (audit_lakeice.py)

Records: Benson, B., Magnuson, J. and Sharma, S. (2000, updated 2020). Global Lake and River Ice Phenology Database, Version 1. NSIDC, doi:10.7265/N5W66HP8. The 'record' column is a mean computed here from its freeze and thaw dates, 1980-81 to 2019-20.

174 lakes. Test half: mae 0.039 of a month, 10 days a year. Shipped field: mae 0.048, 13 days.

| lake | lat | lon | seasons | days iced, record | model | shipped | half |
|---|---|---|---|---|---|---|---|
| LAKE SUPERIOR AT BAYFIELD | 46.81 | -90.81 | 39 | 66 | 139 | 23 | test |
| LAKE SUPERIOR AT MADELINE ISLAND | 46.79 | -90.81 | 27 | 70 | 139 | 23 | fit |
| LAKE BAIKAL | 51.85 | 104.87 | 39 | 102 | 155 | 106 | fit |
| GEORGE | 43.83 | -73.43 | 38 | 67 | 114 | 79 | fit |
| LAKE TELETSKOYE | 51.46 | 87.36 | 10 | 149 | 106 | 184 | fit |
| BURNS LAKE | 54.23 | -125.77 | 10 | 152 | 186 | 171 | test |
| DIEFENBAKER LAKE | 51.28 | -106.83 | 13 | 130 | 158 | 156 | test |
| SAAKSJARVI - SAAKSKOSKI | 61.39 | 22.46 | 32 | 147 | 119 | 107 | test |
| LAKE UTOPIA | 45.10 | -66.73 | 13 | 102 | 128 | 22 | fit |
| GRAND TRAVERSE BAY | 44.77 | -85.62 | 36 | 18 | 44 | 17 | test |
| CRANBERRY | 44.22 | -74.83 | 25 | 130 | 155 | 125 | test |
| GULL LAKE | 42.40 | -85.41 | 37 | 65 | 87 | 88 | fit |
| KUIVAJARVI | 60.78 | 23.84 | 37 | 146 | 125 | 124 | fit |
| ELDON LAKE | 56.87 | -101.08 | 13 | 194 | 214 | 208 | fit |
| KEVOJARVI | 69.76 | 27.01 | 27 | 215 | 195 | 183 | fit |
| LAKE MJOSA - KISA-KAPP | 60.76 | 10.83 | 17 | 50 | 70 | 135 | fit |
| KITUSJARVI (3548) | 62.28 | 24.05 | 33 | 164 | 145 | 135 | test |
| MOHANSIC | 41.28 | -73.81 | 24 | 78 | 97 | 38 | fit |
| LAKE PETAJAVESI (1450) | 62.23 | 25.20 | 16 | 176 | 157 | 137 | fit |
| LAKE KOLIMA (1405) | 62.80 | 25.73 | 16 | 176 | 157 | 161 | test |
| CAZENOVIA | 42.93 | -75.86 | 38 | 100 | 118 | 102 | fit |
| DEADMANS POND | 48.95 | -54.57 | 11 | 160 | 141 | 128 | test |
| HAUKIVESI | 62.11 | 28.61 | 38 | 149 | 167 | 169 | fit |
| ONEIDA | 43.24 | -76.14 | 39 | 92 | 109 | 103 | test |
| RED LAKE - BRUCE CHANNEL | 51.07 | -93.80 | 12 | 164 | 181 | 181 | test |
| LAC DES SABLES | 46.05 | -74.28 | 11 | 144 | 161 | 137 | fit |
| STAR | 44.15 | -75.04 | 25 | 125 | 142 | 120 | test |
| SARANAC LOWER | 44.29 | -74.19 | 25 | 128 | 144 | 124 | test |
| STECHLINSEE | 53.16 | 13.03 | 31 | 38 | 22 | 50 | fit |
| NACKTEN | 62.91 | 14.57 | 34 | 149 | 165 | 173 | fit |
| LANGELMAVESI - KAIVANTO (3506) | 61.42 | 24.15 | 27 | 151 | 135 | 129 | test |
| PELICAN LAKE | 50.12 | -91.90 | 14 | 161 | 176 | 168 | test |
| LOON | 42.48 | -77.56 | 25 | 107 | 123 | 98 | test |
| BONAPARTE | 44.16 | -75.40 | 25 | 110 | 125 | 120 | fit |
| SHABOMEKA | 44.88 | -77.13 | 12 | 125 | 139 | 125 | test |
| KILPISJARVI | 69.05 | 20.79 | 38 | 216 | 202 | 188 | test |
| LAKE MONONA | 43.05 | -89.37 | 39 | 91 | 104 | 111 | test |
| LAKE KALLAVESI (4079) | 62.83 | 27.77 | 38 | 151 | 165 | 170 | test |
| CHAUTAUQUA SOUTH | 42.11 | -79.10 | 25 | 99 | 112 | 89 | fit |
| BOSHKUNG | 45.05 | -78.75 | 14 | 122 | 109 | 130 | fit |
| KUKKIA - PUUTIKKALA (3512) | 61.33 | 24.62 | 35 | 152 | 139 | 137 | fit |
| LAKE GENEVA | 42.57 | -88.50 | 39 | 67 | 80 | 99 | fit |
| LAC BLOUIN | 48.07 | -77.78 | 13 | 158 | 171 | 170 | fit |
| CREE LAKE - CABLE BAY | 57.35 | -107.13 | 12 | 191 | 204 | 190 | test |
| PRIMROSE LAKE | 54.75 | -110.05 | 14 | 165 | 178 | 158 | fit |
| CHATEAGUAY (LOWER) | 44.84 | -74.04 | 24 | 135 | 148 | 127 | test |
| DEVILS LAKE | 43.42 | -89.73 | 24 | 97 | 109 | 111 | test |
| LAKE KOIVUJARVI (1425) | 63.47 | 26.25 | 13 | 180 | 168 | 168 | fit |
| YLA-KIVIJARVI - JURVALA (1488) | 60.95 | 27.76 | 32 | 150 | 162 | 146 | test |
| OUNASJARVI | 68.40 | 23.72 | 38 | 210 | 221 | 222 | test |
| GOUTA | 65.60 | 15.52 | 28 | 189 | 178 | 200 | fit |
| LAKE VATIANJARVI (1423) | 62.47 | 25.88 | 16 | 154 | 166 | 161 | test |
| TITUS | 44.74 | -74.29 | 21 | 137 | 148 | 124 | fit |
| LAC LA RONGE | 55.15 | -105.27 | 14 | 179 | 190 | 179 | fit |
| SIMPELEJARVI | 61.60 | 29.49 | 38 | 155 | 166 | 167 | fit |
| JUKKASJARVI | 67.80 | 20.81 | 39 | 210 | 221 | 217 | fit |
| LAKE KEGONSA | 42.97 | -89.25 | 27 | 100 | 111 | 109 | test |
| WEST OKOBOJI LAKE | 43.39 | -95.16 | 27 | 107 | 118 | 125 | fit |
| UNARI | 67.14 | 25.75 | 27 | 202 | 212 | 215 | test |
| ST. REGIS LOWER | 44.43 | -74.29 | 22 | 138 | 148 | 124 | fit |
| RUNN | 60.47 | 15.59 | 32 | 133 | 123 | 132 | fit |
| BASS LAKE | 44.63 | -79.53 | 13 | 136 | 127 | 59 | test |
| JERISJARVI | 67.95 | 24.01 | 27 | 219 | 229 | 222 | fit |
| LAPPAJARVI - HALKOSAARI (4703) | 63.26 | 23.64 | 36 | 159 | 149 | 141 | fit |
| ALLEQUASH LAKE | 46.04 | -89.62 | 37 | 146 | 155 | 133 | fit |
| JAASJARVI - HARTOLA (1457) | 61.57 | 26.05 | 36 | 152 | 161 | 150 | test |
| REHJA | 64.23 | 27.79 | 37 | 168 | 177 | 177 | test |
| LENTUA | 64.20 | 29.69 | 36 | 176 | 185 | 185 | test |
| GLEN | 41.90 | -75.02 | 25 | 97 | 105 | 101 | test |
| EAST OKOBOJI LAKE | 43.39 | -95.10 | 28 | 118 | 127 | 125 | test |
| DEEP | 43.03 | -77.57 | 25 | 106 | 115 | 30 | fit |
| LAKE ESCANABA | 46.06 | -89.59 | 36 | 143 | 152 | 133 | test |
| BASS-PATTERSON LAKE | 45.95 | -91.63 | 19 | 134 | 142 | 137 | test |
| ALA-KINTAUS (1449) | 62.28 | 25.34 | 24 | 170 | 162 | 158 | test |
| CHAUTAUQUA NORTH | 42.11 | -79.10 | 25 | 95 | 103 | 89 | test |
| OTSEGO | 42.76 | -74.89 | 39 | 73 | 81 | 101 | fit |
| CASSADAGA LOWER | 42.34 | -79.32 | 25 | 99 | 107 | 71 | fit |
| LAKE SALOSJARVI (1451) | 62.12 | 25.20 | 11 | 160 | 152 | 137 | test |
| BIG QUILL LAKE | 51.77 | -104.20 | 11 | 166 | 174 | 177 | test |
| EKAPO LAKE | 50.38 | -102.68 | 14 | 160 | 168 | 148 | test |
| CRYSTAL BOG | 46.00 | -89.60 | 37 | 151 | 159 | 133 | fit |
| STORUMAN | 65.10 | 17.10 | 16 | 171 | 163 | 198 | fit |
| LAKE KEGONSA | 42.97 | -89.25 | 16 | 103 | 111 | 109 | fit |
| PIELINEN | 63.54 | 29.13 | 37 | 164 | 172 | 174 | test |
| SYLVIA | 44.26 | -75.41 | 25 | 95 | 103 | 124 | test |
| LAKE OULUJARVI (5932) | 64.33 | 27.33 | 16 | 185 | 177 | 180 | test |
| PICKLE LAKE | 51.45 | -90.22 | 13 | 181 | 189 | 187 | fit |
| PALOVESI | 61.86 | 23.91 | 35 | 140 | 132 | 127 | test |
| LAKE NASIJARVI (3568) | 61.53 | 23.75 | 38 | 129 | 121 | 125 | fit |
| IISVESI (1433) | 62.67 | 27.04 | 35 | 161 | 168 | 164 | fit |
| LAKE MENDOTA | 43.10 | -89.40 | 39 | 89 | 96 | 111 | fit |
| SHELL LAKE | 45.73 | -91.90 | 39 | 133 | 140 | 136 | test |
| OULUJARVI | 64.30 | 27.30 | 35 | 172 | 179 | 180 | fit |
| BIG GREEN LAKE | 43.80 | -89.00 | 40 | 72 | 66 | 110 | test |
| FRAME LAKE | 62.47 | -114.45 | 12 | 224 | 217 | 159 | test |
| MIRROR LAKE | 43.94 | -71.69 | 26 | 128 | 121 | 131 | test |
| MAPLE LAKE | 46.13 | -89.73 | 25 | 153 | 146 | 133 | test |
| LAKE NEBISH | 46.05 | -89.59 | 35 | 142 | 149 | 133 | test |
| LESTIJARVI | 63.58 | 24.72 | 38 | 169 | 163 | 162 | fit |
| NAAMANKAJARVI | 65.10 | 28.25 | 27 | 192 | 199 | 189 | test |
| NEHMITZSEE | 53.13 | 12.98 | 19 | 61 | 55 | 51 | test |
| BIGWOOD LAKE | 50.12 | -91.90 | 12 | 170 | 176 | 168 | test |
| PLACID | 44.30 | -73.99 | 25 | 128 | 134 | 124 | test |
| SAANIJARVI (1403) | 63.40 | 25.58 | 34 | 170 | 176 | 163 | test |
| BEAR LAKE | 55.18 | -118.88 | 14 | 172 | 166 | 163 | test |
| LAKE ULAKHAN-KUEL | 60.40 | 120.00 | 10 | 220 | 214 | 233 | fit |
| LAKE MUEGGELSEE | 52.44 | 13.65 | 37 | 48 | 53 | 50 | fit |
| FAIR LAKE | 42.48 | -85.33 | 38 | 93 | 99 | 88 | test |
| HANKAVESI - RAUTALAMPI (1436) | 62.62 | 26.83 | 35 | 161 | 166 | 167 | fit |
| BIG MUSKELLUNGE LAKE | 46.02 | -89.62 | 37 | 139 | 145 | 133 | test |
| AHTARINJARVI | 62.76 | 24.05 | 37 | 162 | 157 | 148 | test |
| LAKE CONSTANCE | 47.67 | 9.22 | 40 | 0 | 5 | 6 | fit |
| MEADOW LAKE | 54.13 | -108.52 | 11 | 169 | 174 | 176 | fit |
| LAKE NILAKKA (1429) | 63.13 | 26.55 | 12 | 174 | 169 | 167 | fit |
| ROBERTSON LAKE | 45.32 | -65.88 | 13 | 121 | 126 | 121 | fit |
| (BIG) LONG LAKE | 45.75 | -91.65 | 13 | 134 | 139 | 137 | test |
| CLEARWATER LAKE | 53.97 | -101.10 | 14 | 180 | 185 | 184 | fit |
| KIVIJARVI - SAARENKYLA (1407) | 63.27 | 25.13 | 37 | 164 | 159 | 159 | fit |
| MUTUSJARVI | 68.94 | 26.81 | 34 | 201 | 206 | 196 | fit |
| LITTLE ROCK LAKE | 46.00 | -89.70 | 16 | 150 | 145 | 133 | fit |
| PAIJANNE - TEHI | 61.48 | 25.56 | 27 | 128 | 133 | 136 | fit |
| CHARLIE LAKE | 56.23 | -120.73 | 12 | 169 | 174 | 171 | fit |
| ORSASJON | 61.02 | 14.58 | 34 | 134 | 129 | 143 | fit |
| TROUT BOG | 46.03 | -89.68 | 37 | 153 | 149 | 133 | fit |
| DOUGLAS LAKE | 45.58 | -84.70 | 22 | 127 | 131 | 111 | fit |
| SAND LAKE | 45.92 | -92.18 | 26 | 135 | 139 | 136 | test |
| LAKE VESIJARVI (1462) | 61.18 | 25.54 | 37 | 144 | 148 | 132 | test |
| DRC LAKES | 45.22 | -78.93 | 38 | 132 | 136 | 132 | test |
| MOHONK | 41.76 | -74.16 | 25 | 99 | 95 | 57 | fit |
| LIVOJARVI | 65.98 | 27.97 | 22 | 199 | 203 | 195 | test |
| GENEGANTSLET | 42.51 | -75.77 | 24 | 114 | 117 | 105 | fit |
| VISUVESI | 62.12 | 23.93 | 36 | 144 | 140 | 130 | fit |
| PRIOR | 44.72 | -93.42 | 23 | 123 | 127 | 136 | fit |
| UNNAMED LAKE | 68.65 | -101.73 | 10 | 276 | 279 | 249 | fit |
| ANVIL LAKE | 45.94 | -89.07 | 14 | 144 | 147 | 133 | test |
| LAKE PAIJANNE (1463) | 61.18 | 25.54 | 37 | 134 | 130 | 132 | fit |
| LAKE SARTLAN | 54.54 | 78.35 | 10 | 178 | 181 | 180 | test |
| LAKE BALATON | 46.83 | 17.67 | 14 | 63 | 60 | 60 | fit |
| VESIJARVI - LAHTI (1461) | 60.99 | 25.65 | 34 | 144 | 147 | 126 | fit |
| POROVESI | 63.55 | 27.18 | 27 | 173 | 170 | 167 | fit |
| LAKE NEUSIEDL | 47.82 | 16.75 | 32 | 77 | 74 | 55 | test |
| LONG POND | 44.63 | -76.55 | 13 | 129 | 131 | 125 | fit |
| MYSTERY LAKE | 46.06 | -89.57 | 33 | 149 | 146 | 133 | test |
| BIG TROUT LAKE | 53.83 | -89.87 | 11 | 201 | 204 | 187 | fit |
| ALA-KIVIJARVI - YLA-MUNNI (1489) | 60.94 | 27.51 | 29 | 157 | 160 | 143 | fit |
| PAAJARVI - KARSTULA (1415) | 62.86 | 24.81 | 37 | 163 | 165 | 155 | test |
| KALLSJON | 63.39 | 13.39 | 32 | 125 | 128 | 182 | fit |
| TROUT LAKE | 46.03 | -89.67 | 37 | 133 | 131 | 133 | test |
| SCHOOL SECTION LAKE | 43.60 | -85.27 | 18 | 122 | 119 | 98 | fit |
| LANGELMAVESI S | 61.43 | 24.15 | 15 | 131 | 133 | 129 | test |
| EAGLE LAKE | 41.80 | -86.03 | 22 | 87 | 89 | 85 | fit |
| YORK LAKE | 51.27 | -102.47 | 14 | 168 | 170 | 173 | fit |
| GRACE LAKE | 53.97 | -101.10 | 13 | 187 | 185 | 184 | test |
| KALMARINJARVI (1417) | 62.79 | 25.00 | 35 | 162 | 160 | 158 | fit |
| UNNAMED LAKE | 69.58 | -120.80 | 11 | 263 | 264 | 200 | test |
| LAKE WINNIPEG | 50.62 | -96.98 | 10 | 166 | 168 | 159 | test |
| LAKE BOLSHIE CHANY | 55.33 | 60.54 | 10 | 176 | 177 | 163 | fit |
| SPIRIT LAKE | 43.46 | -95.10 | 27 | 120 | 118 | 125 | fit |
| LAKE UBINSKOYE | 55.32 | 80.05 | 10 | 183 | 182 | 187 | fit |
| SPARKLING LAKE | 46.00 | -89.70 | 37 | 136 | 137 | 133 | test |
| KORVUANJARVI | 65.35 | 28.67 | 26 | 198 | 197 | 192 | fit |
| LONG LAKE | 62.47 | -114.45 | 11 | 216 | 217 | 159 | test |
| LAKE WINGRA | 43.05 | -89.42 | 39 | 109 | 108 | 111 | fit |
| INARI - NELLIM | 68.85 | 28.30 | 37 | 208 | 207 | 194 | test |
| CRYSTAL LAKE | 46.00 | -89.61 | 37 | 137 | 138 | 133 | test |
| SPRUCE LAKE | 46.05 | -89.57 | 36 | 147 | 146 | 133 | fit |
| OIJARVI | 65.62 | 25.93 | 38 | 190 | 190 | 185 | fit |
| PIELAVESI - SAVIA (1427) | 63.20 | 26.67 | 35 | 167 | 168 | 167 | fit |
| LAKE SHISHEBOGAMA | 45.90 | -89.82 | 19 | 147 | 147 | 133 | fit |
| MUURASJARVI (1401) | 63.47 | 25.34 | 36 | 158 | 159 | 161 | test |
| SUMMASJARVI (1419) | 62.68 | 25.35 | 36 | 158 | 158 | 158 | test |
| LAKE VATTERN AT VISINGSO FERRY | 58.03 | 14.41 | 28 | 13 | 13 | 13 | fit |
| ALA-RIEVELI (1468) | 61.34 | 26.20 | 34 | 144 | 145 | 145 | test |
| GREEN | 45.25 | -94.91 | 31 | 132 | 132 | 136 | test |
