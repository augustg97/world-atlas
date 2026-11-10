# Lake ice against NSIDC G01377 (audit_lakeice.py)

Records: Benson, B., Magnuson, J. and Sharma, S. (2000, updated 2020). Global Lake and River Ice Phenology Database, Version 1. NSIDC, doi:10.7265/N5W66HP8. The 'record' column is a mean computed here from its freeze and thaw dates, 1980-81 to 2019-20.

174 lakes. Test half: mae 0.043 of a month, 11 days a year. Shipped field: mae 0.058, 16 days.

| lake | lat | lon | seasons | days iced, record | model | shipped | half |
|---|---|---|---|---|---|---|---|
| LAKE MJOSA - KISA-KAPP | 60.76 | 10.83 | 17 | 50 | 145 | 150 | fit |
| GRAND TRAVERSE BAY | 44.77 | -85.62 | 36 | 18 | 108 | 17 | test |
| LAKE SUPERIOR AT BAYFIELD | 46.81 | -90.81 | 39 | 66 | 132 | 23 | test |
| LAKE SUPERIOR AT MADELINE ISLAND | 46.79 | -90.81 | 27 | 70 | 132 | 23 | fit |
| LAKE CONSTANCE | 47.67 | 9.22 | 40 | 0 | 54 | 57 | fit |
| KALLSJON | 63.39 | 13.39 | 32 | 125 | 178 | 175 | fit |
| LAKE BAIKAL | 51.85 | 104.87 | 39 | 102 | 148 | 167 | fit |
| SAAKSJARVI - SAAKSKOSKI | 61.39 | 22.46 | 32 | 147 | 106 | 101 | test |
| GEORGE | 43.83 | -73.43 | 38 | 67 | 108 | 105 | fit |
| LAKE VATTERN AT VISINGSO FERRY | 58.03 | 14.41 | 28 | 13 | 50 | 55 | fit |
| OTSEGO | 42.76 | -74.89 | 39 | 73 | 108 | 95 | fit |
| BIG GREEN LAKE | 43.80 | -89.00 | 40 | 72 | 105 | 104 | test |
| LAKE PETAJAVESI (1450) | 62.23 | 25.20 | 16 | 176 | 147 | 145 | fit |
| LAKE GENEVA | 42.57 | -88.50 | 39 | 67 | 97 | 93 | fit |
| SYLVIA | 44.26 | -75.41 | 25 | 95 | 123 | 117 | test |
| BURNS LAKE | 54.23 | -125.77 | 10 | 152 | 179 | 164 | test |
| KUIVAJARVI | 60.78 | 23.84 | 37 | 146 | 119 | 118 | fit |
| KEVOJARVI | 69.76 | 27.01 | 27 | 215 | 189 | 175 | fit |
| GULL LAKE | 42.40 | -85.41 | 37 | 65 | 91 | 82 | fit |
| KITUSJARVI (3548) | 62.28 | 24.05 | 33 | 164 | 138 | 140 | test |
| DEADMANS POND | 48.95 | -54.57 | 11 | 160 | 134 | 121 | test |
| NACKTEN | 62.91 | 14.57 | 34 | 149 | 175 | 173 | fit |
| LANGELMAVESI - KAIVANTO (3506) | 61.42 | 24.15 | 27 | 151 | 128 | 128 | test |
| LAKE KOLIMA (1405) | 62.80 | 25.73 | 16 | 176 | 154 | 155 | test |
| DIEFENBAKER LAKE | 51.28 | -106.83 | 13 | 130 | 151 | 149 | test |
| LAKE NEUSIEDL | 47.82 | 16.75 | 32 | 77 | 57 | 50 | test |
| KUKKIA - PUUTIKKALA (3512) | 61.33 | 24.62 | 35 | 152 | 133 | 132 | fit |
| LAKE UTOPIA | 45.10 | -66.73 | 13 | 102 | 122 | 22 | fit |
| STORUMAN | 65.10 | 17.10 | 16 | 171 | 189 | 190 | fit |
| LAKE KOIVUJARVI (1425) | 63.47 | 26.25 | 13 | 180 | 161 | 160 | fit |
| LAKE TELETSKOYE | 51.46 | 87.36 | 10 | 149 | 168 | 177 | fit |
| ALA-KINTAUS (1449) | 62.28 | 25.34 | 24 | 170 | 152 | 148 | test |
| SCHOOL SECTION LAKE | 43.60 | -85.27 | 18 | 122 | 104 | 92 | fit |
| LAKE BALATON | 46.83 | 17.67 | 14 | 63 | 47 | 47 | fit |
| BASS LAKE | 44.63 | -79.53 | 13 | 136 | 120 | 115 | test |
| LAPPAJARVI - HALKOSAARI (4703) | 63.26 | 23.64 | 36 | 159 | 142 | 140 | fit |
| LAKE BOLSHIE CHANY | 55.33 | 60.54 | 10 | 176 | 160 | 160 | fit |
| AHTARINJARVI | 62.76 | 24.05 | 37 | 162 | 146 | 142 | test |
| PLACID | 44.30 | -73.99 | 25 | 128 | 144 | 117 | test |
| LAKE SALOSJARVI (1451) | 62.12 | 25.20 | 11 | 160 | 145 | 145 | test |
| HAUKIVESI | 62.11 | 28.61 | 38 | 149 | 164 | 165 | fit |
| PAIJANNE - TEHI | 61.48 | 25.56 | 27 | 128 | 143 | 143 | fit |
| TROUT BOG | 46.03 | -89.68 | 37 | 153 | 139 | 127 | fit |
| LAKE NILAKKA (1429) | 63.13 | 26.55 | 12 | 174 | 160 | 160 | fit |
| RUNN | 60.47 | 15.59 | 32 | 133 | 119 | 125 | fit |
| LESTIJARVI | 63.58 | 24.72 | 38 | 169 | 156 | 155 | fit |
| FRAME LAKE | 62.47 | -114.45 | 12 | 224 | 210 | 210 | test |
| MIRROR LAKE | 43.94 | -71.69 | 26 | 128 | 115 | 111 | test |
| SAANIJARVI (1403) | 63.40 | 25.58 | 34 | 170 | 157 | 156 | test |
| BONAPARTE | 44.16 | -75.40 | 25 | 110 | 123 | 113 | fit |
| ELDON LAKE | 56.87 | -101.08 | 13 | 194 | 206 | 201 | fit |
| LAKE KALLAVESI (4079) | 62.83 | 27.77 | 38 | 151 | 164 | 165 | test |
| LAKE MENDOTA | 43.10 | -89.40 | 39 | 89 | 102 | 104 | fit |
| SARANAC LOWER | 44.29 | -74.19 | 25 | 128 | 140 | 117 | test |
| CAZENOVIA | 42.93 | -75.86 | 38 | 100 | 112 | 95 | fit |
| MAPLE LAKE | 46.13 | -89.73 | 25 | 153 | 140 | 127 | test |
| NEHMITZSEE | 53.13 | 12.98 | 19 | 61 | 49 | 43 | test |
| LAKE OULUJARVI (5932) | 64.33 | 27.33 | 16 | 185 | 173 | 173 | test |
| BEAR LAKE | 55.18 | -118.88 | 14 | 172 | 160 | 156 | test |
| CRYSTAL BOG | 46.00 | -89.60 | 37 | 151 | 139 | 127 | fit |
| PAAJARVI - KARSTULA (1415) | 62.86 | 24.81 | 37 | 163 | 151 | 148 | test |
| LAKE ULAKHAN-KUEL | 60.40 | 120.00 | 10 | 220 | 208 | 227 | fit |
| LAKE SARTLAN | 54.54 | 78.35 | 10 | 178 | 166 | 167 | test |
| KALMARINJARVI (1417) | 62.79 | 25.00 | 35 | 162 | 151 | 151 | fit |
| LITTLE ROCK LAKE | 46.00 | -89.70 | 16 | 150 | 139 | 127 | fit |
| RED LAKE - BRUCE CHANNEL | 51.07 | -93.80 | 12 | 164 | 175 | 175 | test |
| MOHONK | 41.76 | -74.16 | 25 | 99 | 88 | 52 | fit |
| NAAMANKAJARVI | 65.10 | 28.25 | 27 | 192 | 182 | 183 | test |
| LAC DES SABLES | 46.05 | -74.28 | 11 | 144 | 154 | 131 | fit |
| DEVILS LAKE | 43.42 | -89.73 | 24 | 97 | 107 | 104 | test |
| LAKE MONONA | 43.05 | -89.37 | 39 | 91 | 101 | 104 | test |
| LAKE SHISHEBOGAMA | 45.90 | -89.82 | 19 | 147 | 137 | 127 | fit |
| PELICAN LAKE | 50.12 | -91.90 | 14 | 161 | 171 | 170 | test |
| VISUVESI | 62.12 | 23.93 | 36 | 144 | 134 | 135 | fit |
| STECHLINSEE | 53.16 | 13.03 | 31 | 38 | 48 | 45 | fit |
| KORVUANJARVI | 65.35 | 28.67 | 26 | 198 | 188 | 185 | fit |
| MYSTERY LAKE | 46.06 | -89.57 | 33 | 149 | 139 | 127 | test |
| STAR | 44.15 | -75.04 | 25 | 125 | 135 | 113 | test |
| SIMPELEJARVI | 61.60 | 29.49 | 38 | 155 | 164 | 162 | fit |
| POROVESI | 63.55 | 27.18 | 27 | 173 | 164 | 164 | fit |
| ONEIDA | 43.24 | -76.14 | 39 | 92 | 101 | 98 | test |
| ORSASJON | 61.02 | 14.58 | 34 | 134 | 143 | 145 | fit |
| BOSHKUNG | 45.05 | -78.75 | 14 | 122 | 131 | 124 | fit |
| KIVIJARVI - SAARENKYLA (1407) | 63.27 | 25.13 | 37 | 164 | 155 | 153 | fit |
| PALOVESI | 61.86 | 23.91 | 35 | 140 | 131 | 131 | test |
| ALA-KIVIJARVI - YLA-MUNNI (1489) | 60.94 | 27.51 | 29 | 157 | 149 | 143 | fit |
| SHABOMEKA | 44.88 | -77.13 | 12 | 125 | 133 | 119 | test |
| INARI - NELLIM | 68.85 | 28.30 | 37 | 208 | 200 | 201 | test |
| OIJARVI | 65.62 | 25.93 | 38 | 190 | 182 | 178 | fit |
| GRACE LAKE | 53.97 | -101.10 | 13 | 187 | 179 | 177 | test |
| SPIRIT LAKE | 43.46 | -95.10 | 27 | 120 | 112 | 120 | fit |
| LAKE UBINSKOYE | 55.32 | 80.05 | 10 | 183 | 176 | 176 | fit |
| SPRUCE LAKE | 46.05 | -89.57 | 36 | 147 | 139 | 127 | fit |
| LAKE WINGRA | 43.05 | -89.42 | 39 | 109 | 101 | 104 | fit |
| EAST OKOBOJI LAKE | 43.39 | -95.10 | 28 | 118 | 111 | 120 | test |
| SUMMASJARVI (1419) | 62.68 | 25.35 | 36 | 158 | 151 | 151 | test |
| GREEN | 45.25 | -94.91 | 31 | 132 | 125 | 129 | test |
| PIELINEN | 63.54 | 29.13 | 37 | 164 | 171 | 173 | test |
| LOON | 42.48 | -77.56 | 25 | 107 | 114 | 92 | test |
| CRANBERRY | 44.22 | -74.83 | 25 | 130 | 136 | 119 | test |
| ALLEQUASH LAKE | 46.04 | -89.62 | 37 | 146 | 139 | 127 | fit |
| LAC BLOUIN | 48.07 | -77.78 | 13 | 158 | 165 | 164 | fit |
| CREE LAKE - CABLE BAY | 57.35 | -107.13 | 12 | 191 | 197 | 197 | test |
| LAKE PAIJANNE (1463) | 61.18 | 25.54 | 37 | 134 | 140 | 140 | fit |
| CHATEAGUAY (LOWER) | 44.84 | -74.04 | 24 | 135 | 141 | 121 | test |
| PIELAVESI - SAVIA (1427) | 63.20 | 26.67 | 35 | 167 | 161 | 160 | fit |
| ANVIL LAKE | 45.94 | -89.07 | 14 | 144 | 138 | 127 | test |
| REHJA | 64.23 | 27.79 | 37 | 168 | 174 | 173 | test |
| LONG LAKE | 62.47 | -114.45 | 11 | 216 | 210 | 210 | test |
| TROUT LAKE | 46.03 | -89.67 | 37 | 133 | 139 | 127 | test |
| PRIMROSE LAKE | 54.75 | -110.05 | 14 | 165 | 171 | 166 | fit |
| UNNAMED LAKE | 69.58 | -120.80 | 11 | 263 | 257 | 200 | test |
| JERISJARVI | 67.95 | 24.01 | 27 | 219 | 214 | 214 | fit |
| LAKE WINNIPEG | 50.62 | -96.98 | 10 | 166 | 161 | 161 | test |
| LAC LA RONGE | 55.15 | -105.27 | 14 | 179 | 184 | 183 | fit |
| LIVOJARVI | 65.98 | 27.97 | 22 | 199 | 194 | 190 | test |
| DOUGLAS LAKE | 45.58 | -84.70 | 22 | 127 | 122 | 118 | fit |
| VESIJARVI - LAHTI (1461) | 60.99 | 25.65 | 34 | 144 | 139 | 133 | fit |
| TITUS | 44.74 | -74.29 | 21 | 137 | 141 | 118 | fit |
| LAKE MUEGGELSEE | 52.44 | 13.65 | 37 | 48 | 43 | 43 | fit |
| LENTUA | 64.20 | 29.69 | 36 | 176 | 180 | 179 | test |
| YORK LAKE | 51.27 | -102.47 | 14 | 168 | 164 | 166 | fit |
| LAKE ESCANABA | 46.06 | -89.59 | 36 | 143 | 139 | 127 | test |
| EAGLE LAKE | 41.80 | -86.03 | 22 | 87 | 83 | 79 | fit |
| MOHANSIC | 41.28 | -73.81 | 24 | 78 | 82 | 43 | fit |
| WEST OKOBOJI LAKE | 43.39 | -95.16 | 27 | 107 | 111 | 120 | fit |
| UNNAMED LAKE | 68.65 | -101.73 | 10 | 276 | 272 | 249 | fit |
| LONG POND | 44.63 | -76.55 | 13 | 129 | 125 | 120 | fit |
| LAKE VESIJARVI (1462) | 61.18 | 25.54 | 37 | 144 | 140 | 140 | test |
| BIG TROUT LAKE | 53.83 | -89.87 | 11 | 201 | 198 | 195 | fit |
| CHAUTAUQUA NORTH | 42.11 | -79.10 | 25 | 95 | 98 | 83 | test |
| LAKE NEBISH | 46.05 | -89.59 | 35 | 142 | 139 | 127 | test |
| UNARI | 67.14 | 25.75 | 27 | 202 | 205 | 208 | test |
| SAND LAKE | 45.92 | -92.18 | 26 | 135 | 132 | 130 | test |
| JUKKASJARVI | 67.80 | 20.81 | 39 | 210 | 213 | 210 | fit |
| SPARKLING LAKE | 46.00 | -89.70 | 37 | 136 | 139 | 127 | test |
| LAKE VATIANJARVI (1423) | 62.47 | 25.88 | 16 | 154 | 152 | 152 | test |
| ST. REGIS LOWER | 44.43 | -74.29 | 22 | 138 | 141 | 118 | fit |
| PRIOR | 44.72 | -93.42 | 23 | 123 | 120 | 130 | fit |
| LAKE KEGONSA | 42.97 | -89.25 | 16 | 103 | 100 | 103 | fit |
| LANGELMAVESI S | 61.43 | 24.15 | 15 | 131 | 128 | 128 | test |
| JAASJARVI - HARTOLA (1457) | 61.57 | 26.05 | 36 | 152 | 149 | 150 | test |
| OUNASJARVI | 68.40 | 23.72 | 38 | 210 | 212 | 215 | test |
| ALA-RIEVELI (1468) | 61.34 | 26.20 | 34 | 144 | 147 | 147 | test |
| MUURASJARVI (1401) | 63.47 | 25.34 | 36 | 158 | 156 | 154 | test |
| DRC LAKES | 45.22 | -78.93 | 38 | 132 | 134 | 125 | test |
| LAKE NASIJARVI (3568) | 61.53 | 23.75 | 38 | 129 | 126 | 128 | fit |
| MEADOW LAKE | 54.13 | -108.52 | 11 | 169 | 167 | 169 | fit |
| GENEGANTSLET | 42.51 | -75.77 | 24 | 114 | 112 | 98 | fit |
| CASSADAGA LOWER | 42.34 | -79.32 | 25 | 99 | 101 | 85 | fit |
| DEEP | 43.03 | -77.57 | 25 | 106 | 108 | 102 | fit |
| BASS-PATTERSON LAKE | 45.95 | -91.63 | 19 | 134 | 135 | 130 | test |
| CHARLIE LAKE | 56.23 | -120.73 | 12 | 169 | 167 | 164 | fit |
| CRYSTAL LAKE | 46.00 | -89.61 | 37 | 137 | 139 | 127 | test |
| GOUTA | 65.60 | 15.52 | 28 | 189 | 191 | 193 | fit |
| EKAPO LAKE | 50.38 | -102.68 | 14 | 160 | 162 | 141 | test |
| BIG QUILL LAKE | 51.77 | -104.20 | 11 | 166 | 167 | 170 | test |
| KILPISJARVI | 69.05 | 20.79 | 38 | 216 | 217 | 180 | test |
| PICKLE LAKE | 51.45 | -90.22 | 13 | 181 | 182 | 181 | fit |
| (BIG) LONG LAKE | 45.75 | -91.65 | 13 | 134 | 135 | 130 | test |
| CLEARWATER LAKE | 53.97 | -101.10 | 14 | 180 | 179 | 177 | fit |
| CHAUTAUQUA SOUTH | 42.11 | -79.10 | 25 | 99 | 98 | 83 | fit |
| HANKAVESI - RAUTALAMPI (1436) | 62.62 | 26.83 | 35 | 161 | 160 | 160 | fit |
| SHELL LAKE | 45.73 | -91.90 | 39 | 133 | 134 | 130 | test |
| BIGWOOD LAKE | 50.12 | -91.90 | 12 | 170 | 171 | 170 | test |
| GLEN | 41.90 | -75.02 | 25 | 97 | 96 | 95 | test |
| MUTUSJARVI | 68.94 | 26.81 | 34 | 201 | 202 | 203 | fit |
| ROBERTSON LAKE | 45.32 | -65.88 | 13 | 121 | 120 | 115 | fit |
| IISVESI (1433) | 62.67 | 27.04 | 35 | 161 | 161 | 161 | fit |
| YLA-KIVIJARVI - JURVALA (1488) | 60.95 | 27.76 | 32 | 150 | 151 | 146 | test |
| LAKE KEGONSA | 42.97 | -89.25 | 27 | 100 | 100 | 103 | test |
| OULUJARVI | 64.30 | 27.30 | 35 | 172 | 172 | 173 | fit |
| BIG MUSKELLUNGE LAKE | 46.02 | -89.62 | 37 | 139 | 139 | 127 | test |
| FAIR LAKE | 42.48 | -85.33 | 38 | 93 | 93 | 82 | test |
