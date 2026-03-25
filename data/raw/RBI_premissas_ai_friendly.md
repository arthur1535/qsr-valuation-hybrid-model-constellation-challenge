# RBI / QSR — Premissas limpas para leitura de IA

## Uso pretendido

Este arquivo resume **apenas o que uma IA precisa saber primeiro** para trabalhar em valuation, Monte Carlo ou previsão de ação sem se perder em ruído do Excel.

## Verdade operacional do workbook

- `Scenario_2026` = **premissas editadas conscientemente**.
- `Summary` = **saída do valuation**.
- `Model` = **motor financeiro e operacional**.
- `WACC` = **auxiliar/legado; não assumir como fonte principal do Ke atual**.

## Bloco canônico de premissas

```yaml
asset: QSR
company: Restaurant Brands International
current_price_usd: 73.75
shares_mn: 456
market_cap_usd_mn: 33630
rating: BUY
valuation:
  base_ke: 0.0815
  base_target_price: 86.32717285399377
  base_upside: 0.17053793700330533
  bear_target_price: 69.75294643381923
  bull_target_price: 111.11414841831576
capm_override_2026:
  risk_free: 0.0437
  beta: 0.63
  erp: 0.06
  ke_result: 0.0815
scenario_2026:
  cad_mais_fraco_em_2026e_por_risco_canad_tarifas_pi:
    cell: "Model!S14"
    old: "0.74"
    new: "0.72"
  sofr_2026e_alinhado_a_fed_terminal_3_0_3_25:
    cell: "Model!S16"
    old: "0.033025"
    new: "0.0315"
  th_sss_2026e_ligeiramente_acima:
    cell: "Model!S74"
    old: "0.02"
    new: "0.021"
  bk_sss_2026e_acima_do_base_por_pib_eua_2_5_e_execu:
    cell: "Model!S133"
    old: "0.02"
    new: "0.025"
  bk_net_new_franchise_units_2026e:
    cell: "Model!S124"
    old: "500"
    new: "550"
  popeyes_sss_2026e:
    cell: "Model!S190"
    old: "0.035"
    new: "0.04"
  popeyes_net_new_franchise_units_2026e:
    cell: "Model!S181"
    old: "400"
    new: "420"
  firehouse_sss_2026e:
    cell: "Model!S247"
    old: "0.015"
    new: "0.017"
  payout_2026e_menor_para_reter_caixa_e_investir:
    cell: "Model!S925"
    old: "0.5"
    new: "0.45"
  payout_2027e_menor_mantendo_reinvestimento_no_ramp:
    cell: "Model!T925"
    old: "0.5"
    new: "0.45"
  ke_base_reduzido:
    cell: "Summary!B95"
    old: "0.09"
    new: "0.085"
core_model_outputs_2025e_2031e:
  net_revenue: [13623.70184772935, 10858.909133172507, 13172.081602617538, 14974.732501022594, 17218.175503950464, 20058.360321178596, 23712.64607947972]
  adj_ebitda: [2766.295235801813, 2860.7986649047148, 3291.811650397522, 3655.700928565688, 4229.666589941664, 5004.206984649731, 6040.936613103414]
  net_income: [1950.6244778306996, 1739.0140323659598, 2124.4933153187194, 2467.6021013608724, 2955.1612987031444, 3588.0750477503916, 4366.815352192377]
  fcf: [2590.5251814395533, 1852.3797670368353, 2556.7006417059324, 3054.1386993000147, 3677.583736635177, 4504.827884469172, 5552.375368251162]
  fcff: [3193.897548868814, 2279.024782018453, 2890.6871535405385, 3288.731780703538, 3847.712357454137, 4616.524331548521, 5657.639544647867]
  fcfe: [2328.5251814395533, -1138.8802329631667, -661.2593582940658, -314.96630069998537, 1430.8149866351769, 2841.6260719691727, 5556.040646376163]
  net_debt: [10876.485022421577, 10295.996058588757, 9282.308677826248, 7983.733944924672, 6363.12514382602, 4299.976215560273, 1710.9558663862208]
  payout: [0.65, 0.625, 0.62, 0.61, 0.605, 0.6, 0.6]
```

## O que a IA deve priorizar

1. Usar `base_target_price` e `base_ke` como âncora fundamental.
2. Usar o bloco `scenario_2026` como mudança explícita de premissas.
3. Tratar `net_revenue`, `adj_ebitda`, `fcf`, `fcff`, `fcfe`, `net_debt` e `payout` como série fundamental projetada.
4. Usar os drivers de marca (SSS, units, new units) para explicar crescimento, não para substituir o DCF.

## Drivers de marca mais relevantes para 2026E

| Marca | Driver | 2025E | 2026E | Origem |
|---|---|---|---|---|
| Tim Hortons | Net Revenue | 4,278.57 | 4,705.81 | Model!R22:S22 |
| Tim Hortons | Systemwide Sales | 8,061.87 | 9,031.35 | Model!R48:S48 |
| Tim Hortons | Total Units | 4,586 | 4,690 | Model!R59:S59 |
| Tim Hortons | SSS | 2.90% | 3.04% | Model!R74:S74 |
| Tim Hortons | New Units | 4.77% | 7.46% | Model!R79:S79 |
| Burger King | Net Revenue | 5,511.82 | 1,276.23 | Model!R85:S85 |
| Burger King | Systemwide Sales | 11,499.43 | 11,844.07 | Model!R107:S107 |
| Burger King | Total Units | 7,025 | 7,029 | Model!R118:S118 |
| Burger King | SSS | 2.60% | 2.81% | Model!R133:S133 |
| Burger King | Franchise Units YoY # | -1,029 | 354 | Model!R124:S124 |
| Popeyes | Net Revenue | 741.5102 | 781.9739 | Model!R142:S142 |
| Popeyes | Systemwide Sales | 6,264.96 | 6,549.29 | Model!R164:S164 |
| Popeyes | Total Units | 3,540 | 3,632 | Model!R175:S175 |
| Popeyes | SSS | 1.70% | 1.71% | Model!R190:S190 |
| Popeyes | Franchise Units YoY # | 9 | 92 | Model!R181:S181 |
| Firehouse | Net Revenue | 194.7706 | 202.5966 | Model!R199:S199 |
| Firehouse | Systemwide Sales | 1,284.12 | 1,362.27 | Model!R221:S221 |
| Firehouse | Total Units | 1,449 | 1,649 | Model!R232:S232 |
| Firehouse | SSS | 2.10% | 2.16% | Model!R247:S247 |
| Firehouse | Franchise Units YoY # | 101 | 200 | Model!R238:S238 |

## Leitura curta para algoritmo

- Monte Carlo: usar `current_price_usd`, `base_target_price`, `base_ke`, `net_debt`, `payout` e a distribuição bear/base/bull do Summary.
- LSTM / previsão de preço: não usar o Excel como série temporal de mercado; usar o Excel como **layer de regime fundamental**.
- O workbook é melhor para calibrar **drift, anchor price, downside/upside e coerência de cenário**.
