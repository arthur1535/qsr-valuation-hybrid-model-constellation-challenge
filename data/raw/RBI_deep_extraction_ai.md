# RBI Financial Model — Extração profunda em Markdown

## 1) Objetivo deste arquivo

Este documento reorganiza o Excel `RBI Financial Model.xlsx` em uma estrutura legível para IA. A prioridade é preservar **lógica de leitura**, **hierarquia de confiança** e **endereços de célula** relevantes, em vez de despejar linhas soltas.

## 2) Ordem de leitura recomendada

1. **Scenario_2026** → identificar quais premissas foram explicitamente alteradas.
2. **Summary** → capturar preço atual, grid de `Ke`, `Target Price` e upside.
3. **Model** → usar como motor do case: receita, EBITDA, NI, FCF, FCFF, FCFE, dívida e payout.
4. **Const Challenge** → lembrar que o case exige justificar premissas; as variáveis do modelo são propositalmente editáveis.
5. **Restaurant Sector / UNITS / Metadata / Glossary** → usar como apoio, não como motor do TP.
6. **WACC** → tratar com cautela, porque a aba parece legada e não é a que governa o `Ke` base atual do Summary.

## 3) Mapa das abas e nível de confiança

| Aba | Papel analítico |
|---|---|
| Scenario_2026 | Camada principal de premissas editáveis para 2026E/2027E; usar como override do modelo |
| Summary | Saída resumida do valuation e múltiplos; contém preço atual, Ke, TP e upside |
| Model | Motor principal do modelo; projeções históricas e futuras por marca, IS/BS/CF, FCF/FCFF/FCFE e dívida |
| Const Challenge | Regras do case: as premissas são dummy variables e devem ser justificadas |
| Glossary | Definições dos termos do modelo |
| Restaurant Sector - 4Q2025 | Comps setoriais e múltiplos de pares |
| UNITS | Base geográfica de lojas por marca e país em 2025 |
| Metadata | Definições metodológicas e notas de qualidade de dados |
| WACC | Aba auxiliar/legada; não parece governar o TP base atual do Summary |
| Planilha1 / Planilha2 | Rascunhos auxiliares; baixa prioridade para leitura do valuation |

## 4) Snapshot do valuation em uso

| Item | Valor |
|---|---|
| Ticker / ativo modelado | QSR |
| Preço atual usado no Summary | 73.75 |
| Shares QSR (#mn) | 456 |
| Market Cap implícito (USD mn) | 33,630 |
| Rating exibido | BUY |
| Ke base | 8.15% |
| Target Price base (USD/share) | 86.33 |
| Upside base | 17.05% |
| Bear TP | 69.75 |
| Bull TP | 111.11 |

### 4.1) Grid de sensibilidade do DCF no Summary

| Cenário | Ke | TP (USD/share) | Upside | Origem/formula de Ke |
|---|---|---|---|---|
| Bear+1 | 9.15% | 69.75 | -5.42% | =B94+0.5% |
| Bear | 8.65% | 77.29 | 4.80% | =B95+0.5% |
| Base | 8.15% | 86.33 | 17.05% | 0.0815 |
| Bull | 7.65% | 97.36 | 32.02% | =B95-0.5% |
| Bull+1 | 7.15% | 111.11 | 50.66% | =B96-0.5% |

## 5) Premissas explícitas do cenário (`Scenario_2026`)

| Driver | Célula | Valor anterior | Valor novo | Justificativa | Fonte/nota |
|---|---|---|---|---|---|
| CAD mais fraco em 2026E por risco Canadá/tarifas -> piora translação de TH; conservador vs 0.74 | Model!S14 | 0.74 | 0.72 | CAD mais fraco em 2026E por risco Canadá/tarifas -> piora translação de TH; conservador vs 0.74 | (nota do cenário) + risco Canadá do prompt |
| SOFR 2026E alinhado a Fed terminal 3.0–3.25% | Model!S16 | 0.033 | 0.0315 | SOFR 2026E alinhado a Fed terminal 3.0–3.25% (mid 3.15%) | premissas macro do prompt |
| TH SSS 2026E ligeiramente acima | Model!S74 | 0.02 | 0.021 | TH SSS 2026E ligeiramente acima (macro ok), mas sem exagero por headwind Canadá | premissas macro do prompt |
| BK SSS 2026E acima do base por PIB EUA 2.5% e execução | Model!S133 | 0.02 | 0.025 | BK SSS 2026E acima do base por PIB EUA 2.5% e execução | premissas macro do prompt |
| BK net new franchise units (#) 2026E | Model!S124 | 500 | 550 | BK net new franchise units (#) 2026E: step-up ligado ao plano China (ramp) | https://www.rbi.com/English/news/news-details/2025/RBI-and-CPE-Announce-Joint-Venture-to-Reignite-Growth-at-Burger-King-in-China/default.aspx |
| Popeyes SSS 2026E | Model!S190 | 0.035 | 0.04 | Popeyes SSS 2026E: maior tração do 'chicken war' + macro EUA | premissas macro do prompt |
| Popeyes net new franchise units (#) 2026E | Model!S181 | 400 | 420 | Popeyes net new franchise units (#) 2026E: leve aceleração | premissas macro do prompt |
| Firehouse SSS 2026E | Model!S247 | 0.015 | 0.017 | Firehouse SSS 2026E: comps estáveis com macro favorável | premissas macro do prompt |
| Payout 2026E menor para reter caixa e investir | Model!S925 | 0.5 | 0.45 | Payout 2026E menor para reter caixa e investir (China / crescimento) | https://www.rbi.com/English/news/news-details/2025/RBI-and-CPE-Announce-Joint-Venture-to-Reignite-Growth-at-Burger-King-in-China/default.aspx |
| Payout 2027E menor mantendo reinvestimento no ramp | Model!T925 | 0.5 | 0.45 | Payout 2027E menor mantendo reinvestimento no ramp | https://www.rbi.com/English/news/news-details/2025/RBI-and-CPE-Announce-Joint-Venture-to-Reignite-Growth-at-Burger-King-in-China/default.aspx |
| Ke base reduzido | Summary!B95 | 0.09 | 0.085 | Ke base reduzido (CAPM proxy) vs 9% original, refletindo queda do risk-free | premissas macro do prompt |
| CAPM (para Ke) |  |  |  |  |  |
| Risk-free (Rf) | Model!S16 |  | 0.0437 | Proxy: SOFR 2026E | premissas macro do prompt |
| Beta (β) [input] |  |  | 0.63 | Beta setorial (ajustável) | definir fonte preferida |
| Equity Risk Premium (ERP) [input] |  |  | 0.06 | ERP global (ajustável) | definir fonte preferida |
| Ke = Rf + β*ERP [calc] |  |  | 0.0815 | Ke calculado (confira) e aplicado em Summary!B95 |  |

### 5.1) CAPM/Ke explícito na aba de cenário

| Componente | Origem | Valor |
|---|---|---|
| Risk-free (Rf) | Model!S16 | 4.37% |
| Beta (β) | - | 0.63 |
| Equity Risk Premium (ERP) | - | 6.00% |
| Ke = Rf + β×ERP | - | 8.15% |

## 6) Regras do case (`Const Challenge`)

- O modelo deve ser usado como **base** para análise e projeção.
- O case explicitamente diz que os grupos podem usar abordagens melhores de forecast.
- A diferenciação vem da **qualidade da lógica das premissas**: acelerar ou não SSS de BK, expandir ou contrair margem EBITDA, etc.
- Com exceção de premissas macro, as demais entradas são essencialmente **dummy variables** e devem ser defendidas.

## 7) Saídas centrais do `Model` (2024A–2031E)

| Linha | 2024A | 2025E | 2026E | 2027E | 2028E | 2029E | 2030E | 2031E |
|---|---|---|---|---|---|---|---|---|
| Net Revenue | 8,406 | 13,623.70 | 10,858.91 | 13,172.08 | 14,974.73 | 17,218.18 | 20,058.36 | 23,712.65 |
| Adj. EBITDA (Constellation) | 2,593 | 2,766.30 | 2,860.80 | 3,291.81 | 3,655.70 | 4,229.67 | 5,004.21 | 6,040.94 |
| Reported Net Income | 1,445 | 1,950.62 | 1,739.01 | 2,124.49 | 2,467.60 | 2,955.16 | 3,588.08 | 4,366.82 |
| CFO | 1,503 | 2,950.49 | 2,222.50 | 2,924.85 | 3,326.19 | 3,941.90 | 4,765.02 | 5,821.52 |
| Capex | -201 | -359.9682 | -370.122 | -368.1518 | -272.0476 | -264.3198 | -260.1925 | -269.1456 |
| FCF | 762 | 2,590.53 | 1,852.38 | 2,556.70 | 3,054.14 | 3,677.58 | 4,504.83 | 5,552.38 |
| FCFF | 1,271.59 | 3,193.90 | 2,279.02 | 2,890.69 | 3,288.73 | 3,847.71 | 4,616.52 | 5,657.64 |
| FCFE | 981 | 2,328.53 | -1,138.88 | -661.2594 | -314.9663 | 1,430.81 | 2,841.63 | 5,556.04 |
| Gross Debt | 13,677 | 13,415 | 10,423.74 | 7,205.78 | 3,836.67 | 1,589.91 | -73.2956 | -69.6303 |
| Cash | 1,334 | 2,538.51 | 127.7439 | -2,076.53 | -4,147.06 | -4,773.22 | -4,373.27 | -1,780.59 |
| Net Debt | 12,343 | 10,876.49 | 10,296.00 | 9,282.31 | 7,983.73 | 6,363.13 | 4,299.98 | 1,710.96 |
| ND/EBITDA (Constellation) | 4.7601 | 3.9318 | 3.599 | 2.8198 | 2.1839 | 1.5044 | 0.8593 | 0.2832 |
| Shareholders' Equity | 4,843 | 5,706.10 | 6,436.32 | 7,328.76 | 8,380.99 | 9,655.94 | 11,238.96 | 13,156.11 |
| Payout | n.m. | 65.00% | 62.50% | 62.00% | 61.00% | 60.50% | 60.00% | 60.00% |

## 8) Drivers operacionais por marca (2024A–2027E)

### Tim Hortons

| Métrica | 2024A | 2025E | 2026E | 2027E | Faixa de células |
|---|---|---|---|---|---|
| Net Revenue | 4,038 | 4,278.57 | 4,705.81 | 5,204.85 | Model!Q22:T22 |
| Systemwide Sales | 7,479 | 8,061.87 | 9,031.35 | 10,583.25 | Model!Q48:T48 |
| Total Units | 4,531 | 4,586 | 4,690 | 4,770 | Model!Q59:T59 |
| SSS | 4.00% | 2.90% | 3.04% | 3.29% | Model!Q74:T74 |
| FX | -1.26% | -0.01% | 1.16% | 2.30% | Model!Q77:T77 |
| New Units | 0.0052 | 0.0477 | 0.0746 | 0.109 | Model!Q79:T79 |
| Marginal Productivity | 1.6635 | 3.9278 | 3.2913 | 6.3928 | Model!Q80:T80 |

### Burger King

| Métrica | 2024A | 2025E | 2026E | 2027E | Faixa de células |
|---|---|---|---|---|---|
| Net Revenue | 1,450 | 5,511.82 | 1,276.23 | 1,314.29 | Model!Q85:T85 |
| Systemwide Sales | 11,484 | 11,499.43 | 11,844.07 | 12,242.46 | Model!Q107:T107 |
| Total Units | 7,082 | 7,025 | 7,029 | 7,033 | Model!Q118:T118 |
| Franchise Units YoY # | -84 | -1,029 | 354 | 304 | Model!Q124:T124 |
| SSS | 1.02% | 2.60% | 2.81% | 3.14% | Model!Q133:T133 |
| New Units % | -0.93% | -2.40% | 0.18% | 0.21% | Model!Q136:T136 |
| Marginal Productivity | 1.0726 | 2.9858 | 3.2291 | 3.7252 | Model!Q137:T137 |

### Popeyes

| Métrica | 2024A | 2025E | 2026E | 2027E | Faixa de células |
|---|---|---|---|---|---|
| Net Revenue | 768 | 741.5102 | 781.9739 | 820.4681 | Model!Q142:T142 |
| Systemwide Sales | 6,124 | 6,264.96 | 6,549.29 | 6,908.19 | Model!Q164:T164 |
| Total Units | 3,520 | 3,540 | 3,632 | 3,748 | Model!Q175:T175 |
| Franchise Units YoY # | 69 | 9 | 92 | 116 | Model!Q181:T181 |
| SSS | 0.50% | 1.70% | 1.71% | 1.75% | Model!Q190:T190 |
| New Units % | 3.54% | 0.59% | 2.78% | 3.66% | Model!Q193:T193 |
| Marginal Productivity | 0.9539 | 1.0415 | 1.0706 | 1.1474 | Model!Q194:T194 |

### Firehouse

| Métrica | 2024A | 2025E | 2026E | 2027E | Faixa de células |
|---|---|---|---|---|---|
| Net Revenue | 213 | 194.7706 | 202.5966 | 224.76 | Model!Q199:T199 |
| Systemwide Sales | 1,233 | 1,284.12 | 1,362.27 | 1,444.39 | Model!Q221:T221 |
| Total Units | 1,345 | 1,449 | 1,649 | 1,849 | Model!Q232:T232 |
| Franchise Units YoY # | 80 | 101 | 200 | 200 | Model!Q238:T238 |
| SSS | -1.07% | 2.10% | 2.16% | 2.24% | Model!Q247:T247 |
| New Units % | 3.78% | 2.00% | 3.84% | 3.71% | Model!Q250:T250 |
| Marginal Productivity | 0.5977 | 0.2592 | 0.2782 | 0.3056 | Model!Q251:T251 |

## 9) Pares setoriais (`Restaurant Sector - 4Q2025`)

| Company | Ticker | Market Cap | P/E | P/B | P/EBIT | P/EBITDA | Dividend Yield |
|---|---|---|---|---|---|---|---|
| McDONALD’S CORPORATION | MCD | 217,119,140,423 | 25.36 |  | 17.52 | 16.9 | 2.35% |
| Starbucks Corporation | SBUX | 96,931,646,086 | 70.81 |  | 35.82 |  | 2.88% |
| CHIPOTLE MEXICAN GRILL, INC. | CMG | 48,189,651,000 | 31.38 | 17.02 | 24.89 | 20.98 |  |
| YUM! BRANDS, INC. | YUM | 41,818,349,729 | 26.82 |  | 16.25 | 15.04 | 1.88% |
| RESTAURANT BRANDS INTERNATIONAL INC. | QSR | 21,586,774,875 | 28.78 | 5.94 | 9.8 |  | 3.63% |
| DARDEN RESTAURANTS INC | DRI | 20,117,129,726 | 17.92 | 9.67 | 13.77 | 10.06 | 3.32% |
| Yum China Holdings, Inc. | YUMC | 16,856,824,829 | 18.15 | 3.13 | 13.07 | 9.7 | 1.01% |
| Domino’s Pizza, Inc. | DPZ | 14,311,113,325 | 23.78 |  | 15 | 14.66 | 1.64% |
| TEXAS ROADHOUSE, INC. | TXRH | 11,035,868,871 | 37.94 | 7.55 | 23.25 | 16.2 | 1.62% |
| CAVA Group, Inc. | CAVA | 7,000,122,742 | 109.82 | 8.98 | 126.62 | 54.29 |  |

## 10) Geografia de lojas (`UNITS`) — maiores países por total de unidades

| País | Total | Tim Hortons | Burger King | Popeyes | Firehouse |
|---|---|---|---|---|---|
| United States | 11,804 | 683 | 6,649 | 3,196 | 1,276 |
| Canada | 4,834 | 3,903 | 376 | 382 | 173 |
| China | 2,217 | 896 | 1,247 | 74 | 0 |
| Turkey | 1,296 | 0 | 803 | 493 | 0 |
| Spain | 1,190 | 13 | 998 | 179 | 0 |
| Brazil | 1,088 | 0 | 985 | 95 | 8 |
| Germany | 757 | 0 | 757 | 0 | 0 |
| United Kingdom | 752 | 70 | 574 | 108 | 0 |
| Mexico | 724 | 187 | 467 | 53 | 17 |
| India | 693 | 44 | 577 | 72 | 0 |
| France | 647 | 0 | 617 | 30 | 0 |
| South Korea | 600 | 24 | 552 | 24 | 0 |
| Australia | 480 | 0 | 480 | 0 | 0 |
| Saudi Arabia | 426 | 184 | 156 | 86 | 0 |
| Japan | 337 | 0 | 337 | 0 | 0 |

## 11) Glossário mínimo

| Sigla | Definição |
|---|---|
| BoP | Beginning of Period |
| Capex | Capital Expenditures |
| CFF | Cash flow from financing activities |
| CFI | Cash Flow from from investing activities |
| CFO | Cash Flow from operating activities |
| D&A | Depreciation and amortization |
| DVPS | Dividends per share |
| EoP | End of Period |
| EPS | Earnings per Share |
| EV | Enterprise Value |
| FCF | Free cash flow |
| FCFE | Free cash flow to equity |

## 12) Observações analíticas importantes para IA

- **`Scenario_2026` é a camada de override**. Ao interpretar o workbook, use os drivers dessa aba como premissas deliberadas do case.
- **`Summary` é a camada de saída**, não a camada que deve ser editada primeiro.
- **`Model` é o motor**: tudo que importa para Monte Carlo, DCF e ponte entre operacional e valuation está ali.
- A aba **`WACC` parece auxiliar/legada**: ela carrega insumos em português, referências a Brasil e um cálculo que não coincide diretamente com o `Ke` base atual do Summary. Portanto, ela não deve sobrepor o `Ke` explícito do `Scenario_2026` + Summary sem validação manual.
- Para algoritmo de previsão de ação, o workbook é melhor usado como **ancoragem fundamental** (drift, TP, payout, desalavancagem, FCF) do que como série temporal pura.
- `Planilha1` e `Planilha2` têm baixa prioridade; tratá-las como rascunho auxiliar.

## 13) Bloco machine-readable (YAML-lite)

```yaml
ticker: QSR
current_price_usd: 73.75
shares_mn: 456
market_cap_usd_mn: 7000122742
rating: BUY
base_ke: 0.0815
base_target_price: 86.32717285399377
base_upside: 0.17053793700330533
scenario_overrides:
  - key: cad_mais_fraco_em_2026e_por_risco_canad_tarifas_piora_transl
    label: "CAD mais fraco em 2026E por risco Canadá/tarifas -> piora translação de TH; conservador vs 0.74"
    cell: "Model!S14"
    old_value: "0.74"
    new_value: "0.72"
  - key: sofr_2026e_alinhado_a_fed_terminal_3_0_3_25
    label: "SOFR 2026E alinhado a Fed terminal 3.0–3.25%"
    cell: "Model!S16"
    old_value: "0.033025"
    new_value: "0.0315"
  - key: th_sss_2026e_ligeiramente_acima
    label: "TH SSS 2026E ligeiramente acima"
    cell: "Model!S74"
    old_value: "0.02"
    new_value: "0.021"
  - key: bk_sss_2026e_acima_do_base_por_pib_eua_2_5_e_execu_o
    label: "BK SSS 2026E acima do base por PIB EUA 2.5% e execução"
    cell: "Model!S133"
    old_value: "0.02"
    new_value: "0.025"
  - key: bk_net_new_franchise_units_2026e
    label: "BK net new franchise units (#) 2026E"
    cell: "Model!S124"
    old_value: "500"
    new_value: "550"
  - key: popeyes_sss_2026e
    label: "Popeyes SSS 2026E"
    cell: "Model!S190"
    old_value: "0.035"
    new_value: "0.04"
  - key: popeyes_net_new_franchise_units_2026e
    label: "Popeyes net new franchise units (#) 2026E"
    cell: "Model!S181"
    old_value: "400"
    new_value: "420"
  - key: firehouse_sss_2026e
    label: "Firehouse SSS 2026E"
    cell: "Model!S247"
    old_value: "0.015"
    new_value: "0.017"
  - key: payout_2026e_menor_para_reter_caixa_e_investir
    label: "Payout 2026E menor para reter caixa e investir"
    cell: "Model!S925"
    old_value: "0.5"
    new_value: "0.45"
  - key: payout_2027e_menor_mantendo_reinvestimento_no_ramp
    label: "Payout 2027E menor mantendo reinvestimento no ramp"
    cell: "Model!T925"
    old_value: "0.5"
    new_value: "0.45"
  - key: ke_base_reduzido
    label: "Ke base reduzido"
    cell: "Summary!B95"
    old_value: "0.09"
    new_value: "0.085"
  - key: capm_para_ke
    label: "CAPM (para Ke)"
    cell: ""
    old_value: "None"
    new_value: "None"
  - key: risk_free_rf
    label: "Risk-free (Rf)"
    cell: "Model!S16"
    old_value: "None"
    new_value: "0.0437"
  - key: beta_input
    label: "Beta (β) [input]"
    cell: ""
    old_value: "None"
    new_value: "0.63"
  - key: equity_risk_premium_erp_input
    label: "Equity Risk Premium (ERP) [input]"
    cell: ""
    old_value: "None"
    new_value: "0.06"
  - key: ke_rf_erp_calc
    label: "Ke = Rf + β*ERP [calc]"
    cell: ""
    old_value: "None"
    new_value: "0.0815"
priority_read_order:
  - Scenario_2026
  - Summary
  - Model
  - Const Challenge
  - Restaurant Sector - 4Q2025
  - UNITS
```