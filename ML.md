# Risco & Precificação — README (LOGR1 + LINR1 + API)

Este README “abre a caixa-preta” do sistema construído no hackathon: como estimamos **risco (PD)**, como o traduzimos para **score 0–1000 e bandas**, como **precificamos** a taxa mensal sugerida (PD → *rate*), como **checamos unit economics**, e como isso aparece no **endpoint**.

---

## Visão geral

* **LOGR1 (PD)**: pipeline scikit-learn que entrega `PD_12m` calibrado.
* **Scorecard (odds-to-score)**: mapeia PD → score 0–1000 e banda A–E (parametrizado em YAML).
* **LINR1 (pricing)**: converte PD → taxa mensal bruta via regressão linear (com termo quadrático opcional) e **isotônica** (opcional) para monotonicidade, com **caps**.
* **Unit economics**: sanity check do “vale a pena emprestar?” (funding + opex + risco + margem).
* **API**: `POST /risk/score` recebe *features* (+ `amount`, `term_months`) e retorna `{pd, score, band, rate, pmt, cet, unit_economics, ...}`.

Estrutura de pastas relevante:

```
mlops/
  conf/
    scoring.yaml
    pricing.yaml
  training/
    risk__LOGR1/           # treino do PD
      outputs/models/pd_logr1.joblib
    pricing__LINR1/        # treino do pricing
      data/pricing_train.csv
      outputs/models/pricing_linr1.joblib
risk/
  services/registry.py     # carregamento de artifacts (PD, scorecard, pricing)
  views.py                 # endpoint /risk/score
  serializers.py           # ScoreRequest (+ montagem do feature vector)
  calculators/             # pmt, CET etc.
```

Env vars principais:

* `PD_MODEL_PATH` (default: `mlops/training/risk__LOGR1/outputs/models/pd_logr1.joblib`)
* `SCORING_CONF` (default: `mlops/conf/scoring.yaml`)
* `PRICING_MODEL_PATH` (default: `mlops/training/pricing__LINR1/outputs/models/pricing_linr1.joblib`)
* `PRICING_CONF_PATH` (default: `mlops/conf/pricing.yaml`)

---

## 1) PD (probability of default) — LOGR1

**O que faz**
Pipeline scikit-learn serializado por `joblib` com:

1. `SimpleImputer(strategy='median')`
2. `ColumnTransformer` (inclui `PolynomialFeatures` em um bloco de colunas)
3. (Feature de interação) **`ambos` = beneficio_ativo * emprego_ativo**
4. `RobustScaler`
5. `LogisticRegression(penalty='elasticnet', solver='saga')`
6. **Calibração** `CalibratedClassifierCV` (isotônica/sigmoid) → `predict_proba` confiável.

**Entrada:** `X = [req.to_feature_vector()]` na ordem esperada.
**Saída:** `pd_hat = model.predict_proba(X)[0, 1]` (PD em 12m).

> ⚠️ **Importante**: o modelo em produção foi treinado esperando **16 colunas**, incluindo a coluna derivada **`ambos`**. Certifique-se de que `ScoreRequest.to_feature_vector()` **monta `ambos`** (0/1) **ou** ajuste o pipeline para calcular internamente. Se faltar `ambos`, você verá o erro “X has 15 features, but ColumnTransformer is expecting 16”.

**Onde fica**

* Carregamento: `registry.get_pd_model()`
* Uso: `risk/views.py` → `model.predict_proba(X)`

---

## 2) Score 0–1000 (odds-to-score) + Bandas

**O que faz**
Converte PD → score com a fórmula padrão de mercado parametrizada no YAML (escala semelhante à referência pública da Serasa, ajustável):

[
\text{Score} = S_0 + \frac{\text{PDO}}{\ln 2}\cdot \ln!\left(\frac{(1-PD)/PD}{O_0}\right)
]

**Bandas** A–E conforme *cuts* do YAML.

**Onde fica**

* `Scorecard(conf).score_and_band(pd_hat)`
* Config: `mlops/conf/scoring.yaml`

**Exemplo de `scoring.yaml` (benchmark-like)**

```yaml
scorecard:
  S0: 700      # âncora (score na razão de odds O0)
  O0: 20       # odds na âncora (20:1 ≈ 4,76% PD)
  PDO: 50      # Points to Double the Odds
limits:
  pd_floor: 0.002
  pd_ceiling: 0.60
  score_min: 0
  score_max: 1000
bands:
  A: {min: 800}
  B: {min: 680}
  C: {min: 580}
  D: {min: 450}
  E: {min: 0}
round_score: true
```

**Por que assim**
Score facilita comunicação; **decisão e pricing seguem o PD**.

**Checklist de revisão**

* **Parâmetros:** `S0`, `O0`, `PDO` coerentes com seu portfólio (S0↑/O0↑ desloca curva; PDO↓ torna curva mais “íngreme”).
* **Bandas:** cortes refletem sua política/funding.
* **Monotonicidade:** PD↑ → score↓ (teste com grid de PD).
* **Robustez:** `clip` de PD [pd_floor, pd_ceiling].
* **Transparência:** retorne no JSON

  ```json
  "scorecard": {"S0":700,"PDO":50,"O0":20,"band_cuts":{"A":800,"B":680,"C":580,"D":450}}
  ```

---

## 3) Pricing (PD → taxa mensal sugerida) — LINR1

**O que faz**
Artefato `pricing_linr1.joblib` com:

* `lr`: Regressão Linear (com `PD` e opcional `PD^2`)
* `iso` (opcional): regressão isotônica para curva **suave e monótona**
* `caps`: dicionário com `min_rate_monthly`/`max_rate_monthly`

**Wrapper em runtime**
`_PricingWrapper.suggest_rate(pd)`:

1. Detecta grau (1/2) via `coef_`.
2. Monta `X = [PD, PD^2]` se preciso → `lr.predict`.
3. Se existir `iso`, usa `iso.predict(PD)` (suaviza/monotoniza).
4. Aplica **caps**.
5. Exponibiliza metadados: `mode`, `poly_degree`, `caps`.

**Onde fica**

* Carregamento: `registry.get_pricing()` (lê `PRICING_MODEL_PATH` e `PRICING_CONF_PATH` para caps de *fallback*).
* Wrapper: `risk/services/registry.py`.

**Por que assim**

* Com histórico: LINR1 aprende PD→taxa.
* Sem histórico: gera curva-alvo coerente com **unit economics** (Seção 4) e treina para reproduzi-la. Com isotônica, garante **PD↑ → taxa↑**.

**Teste rápido**

* `taxa(1%) < taxa(5%)`
* Fora de range: cap **min/max** prevalece.

**Telemetria sugerida**
Logue `{pd, rate_raw, rate_final, poly_degree, mode}`.

---

## 4) Unit economics (vale a pena emprestar?)

**Ideia**: taxa deve cobrir **funding + opex + risco (EL)** e **margem**.

* **EL ≈ PD × LGD × EAD**

  * PD: do LOGR1 (12m).
  * LGD: perda condicional (ex.: 45% crédito pessoal sem garantia).
  * EAD (regra rápida em Price): **≈ 50% do principal**.
  * Logo, **EL do contrato** ≈ `PD × LGD × 0,5 × P`.

* **Funding**: custo do dinheiro (ex.: 0,8% a.m.).

* **Opex**: 0,3% a.m. (exemplo).

* **Margem alvo**: 0,2–0,5% a.m.

**Regra simplificada para taxa mínima mensal**
[
i_{\min} \approx \text{funding} + \text{opex} + \underbrace{(EL/P)/(n/12)}_{\text{“pró-rata” anual→mensal}} + \text{margem}
]

> Alternativa: **regra k·PD**
> ( i \approx \text{funding} + \text{opex} + k \cdot PD )
> Calibre (k) para cobrir EL **em média** e manter monotonicidade.

**Conferência**
Depois de definir `i`, calcule **PMT** (Price) e simule **cashflow**: margem esperada ≥ 0.

---

## 5) API — `POST /risk/score`

**Entrada (JSON)**

```json
{
  "features": {
    "beneficio_ativo":0,
    "tempo_beneficio_meses":0,
    "emprego_ativo":1,
    "tempo_emprego_meses":36,
    "renda_media_6m":4200.0,
    "coef_var_renda":0.22,
    "pct_meses_saldo_neg_6m":0.17,
    "utilizacao_cartao":0.62,
    "pct_minimo_pago_3m":0.28,
    "num_faturas_vencidas_3m":1,
    "endividamento_total":32000.0,
    "parcelas_renda":0.36,
    "DPD_max_12m":10,
    "idade":39,
    "tempo_rel_banco_meses":84,

    "ambos": 1  // <-- IMPORTANTÍSSIMO se o pipeline espera 16 colunas
  },
  "amount": 10000,
  "term_months": 24,
  "fees": { }   // opcional: IOF/seguro/tarifas para CET
}
```

> ✅ Se preferir não mandar `"ambos"`, implemente no `ScoreRequest`:
> `ambos = int(bool(beneficio_ativo) and bool(emprego_ativo))`
> e inclua no vetor final — assim você evita o erro “X has 15 features … expected 16”.

**Saída (exemplo)**

```json
{
  "pd": 0.067388,
  "score": 673,
  "band": "C",
  "scorecard": {
    "S0": 700, "PDO": 50, "O0": 20,
    "band_cuts": {"A":800,"B":680,"C":580,"D":450}
  },
  "rate_monthly": 0.03013,
  "rate_yearly_eff": 0.427921,
  "model": {"name": "pd_logr1", "path": "mlops/training/risk__LOGR1/outputs/models/pd_logr1.joblib"},
  "pricing": {
    "mode": "linr+isotonic",
    "poly_degree": 2,
    "caps": {"min_rate_monthly": 0.017, "max_rate_monthly": 0.045}
  },
  "unit_economics": {
    "el_over_P": 0.015162,
    "risk_component_monthly": 0.007581,
    "funding": 0.018,
    "opex": 0.004,
    "margin_target": 0.006,
    "i_min_monthly": 0.035581,
    "rate_vs_min_bps": -55,
    "ok_to_lend": false
  },
  "installment": 591.3,
  "cet_monthly": 0.03013,
  "cet_yearly": 0.427921,
  "fees": {}
}
```

**Curl**

```bash
curl -sS -X POST http://127.0.0.1:8000/risk/score   -H "Content-Type: application/json"   -d '{
    "features": {
      "beneficio_ativo":0,"tempo_beneficio_meses":0,
      "emprego_ativo":1,"tempo_emprego_meses":36,
      "renda_media_6m":4200.0,"coef_var_renda":0.22,
      "pct_meses_saldo_neg_6m":0.17,"utilizacao_cartao":0.62,
      "pct_minimo_pago_3m":0.28,"num_faturas_vencidas_3m":1,
      "endividamento_total":32000.0,"parcelas_renda":0.36,
      "DPD_max_12m":10,"idade":39,"tempo_rel_banco_meses":84,
      "ambos":1
    },
    "amount": 10000,
    "term_months": 24
  }' | jq .
```

---

## 6) Como treinar e avaliar o **pricing**

### 6.1 Treinar o LINR1

```bash
python mlops/training/pricing__LINR1/train_pricing.py \
  --conf mlops/conf/pricing.yaml \
  --outdir mlops/training/pricing__LINR1/outputs \
  --labels historical \
  --csv mlops/training/pricing__LINR1/data/pricing_train.csv
```

### 6.2 Avaliar rapidamente

```bash
python mlops/training/pricing__LINR1/eval_pricing_short.py   --model mlops/training/pricing__LINR1/outputs/models/pricing_linr1.joblib   --conf  mlops/conf/pricing.yaml   --csv   mlops/training/pricing__LINR1/data/pricing_train.csv
```

---

## 7) Parâmetros de **pricing.yaml** (exemplo)

```yaml
caps:
  min_rate_monthly: 0.017   # 1,7% a.m.
  max_rate_monthly: 0.045   # 4,5% a.m.
unit_economics:
  lgd: 0.45
  funding_monthly: 0.008    # 0,8% a.m.
  opex_monthly: 0.003       # 0,3% a.m.
  margin_monthly: 0.002     # 0,2% a.m.
defaults:
  use_isotonic: true
  poly_degree: 2
```

---

## 8) Boas práticas e melhorias

**Para o PD (LOGR1)**

* **CV/Tuning**: `StratifiedKFold`, grid em `C`, `l1_ratio`, `penalty`, `degree`.
* **Calibração**: isotônica melhora probabilidades.
* **Features**: teste interações, winsorize *outliers*, *binning* para monotonicidade.
* **AUC, KS, Brier** como *KPIs*; monitore drift de *features* e PD.

**Para o Pricing (LINR1)**

* **Isotônica**: impor monotonicidade PD→taxa.
* **Caps**: política de `min`/`max`.
* **Telemetria**: logue `pd`, `rate_raw`, `rate_final`, `ok_to_lend`, distâncias aos caps.
* **Validação**: teste pontos canônicos (1%, 5%, 10% PD).
* **Unit economics**: valide `i_min` vs `rate_final` e calcule *cashflow*.

**API/Operação**

* **Auditoria**: retorne `model.path`, *scorecard params*, *pricing meta*.
* **Erros amigáveis**: se faltar coluna (ex.: `ambos`), retorne dica clara.
* **Testes**: smoke do endpoint e *unit tests* de `ScoreRequest`/`pmt`/`CET`.

---

## 9) Exemplo numérico (sanity check)

* `P=10.000`, `n=24`, `PD=3%`, `LGD=45%`
* `Funding=0,80% a.m.`, `Opex=0,30% a.m.`, `Margem=0,20% a.m.`
* `EAD≈50%P` → `EL≈0,03×0,45×0,5×10.000=R$67,5` → `EL/P=0,675%`
* Risco mensal (pró-rata 24m): `0,3375% a.m.`
* **i_min** ≈ 0,80% + 0,30% + 0,3375% + 0,20% = **1,6375% a.m.**
* Sugerir **1,70% a.m.** (folga).
* **PMT** (Price): ≈ **R$ 494,36**; **CET a.a.** ≈ **22,3%** (sem tarifas).

---

## 10) Resolução de problemas comuns

* **“X has 15 features, but ColumnTransformer is expecting 16”**
  → Inclua a coluna **`ambos`** no vetor (ou ajuste o pipeline para criá-la).
  → Em `ScoreRequest.to_feature_vector()`:
  `ambos = int(bool(beneficio_ativo) and bool(emprego_ativo))`.

* **“rest_framework / oauth2_provider não encontrado”**
  → `pip install djangorestframework django-oauth-toolkit` e adicione a `INSTALLED_APPS`.

* **Taxa fora da política**
  → ajuste `caps` no `pricing.yaml` ou parâmetros do LINR1 (grau, isotônica).

---

## 11) Política de crédito

* “A sua taxa é função do seu **risco (PD)**, mais **custo de funding**, **operacional** e uma **margem mínima**.”
* Mostrar **3 motivos** (features) que mais impactaram o score (coeficientes LOGR1).
* Garantir **monotonicidade** (PD↑ → taxa↑).
* Aplicar **floors/ceilings** por **banda** (ex.: A: 1,3–1,8% a.m.; E: nega).

---

## 12) Reprodutibilidade

* Versione:

  * `pd_logr1.joblib` + métricas (AUC/KS/Brier).
  * `pricing_linr1.joblib` + *scatter PD→rate* com/sem isotônica.
  * `scoring.yaml` e `pricing.yaml`.
* Emita um relatório `outputs/reports/risco_baseline.json` com *hash* dos artifacts, datas e parâmetros.

---

## 13) Roadmap (curto)

* **Explicar motivos** (shapley/coeficientes) no JSON.
* **Alertas**: drift de distribuição de *features* e PD.
* **Tuning automatizado** (pipeline de grid em CI).
* **Simulador CET completo** (com IOF/seguro/tarifas) e *what-if* de caps.

---

Qualquer pessoa que leia este README consegue: (i) treinar o PD, (ii) calibrar o score e as bandas, (iii) treinar/ajustar o pricing com caps/iso, (iv) validar unit economics, e (v) consumir o endpoint com *payload* correto (incluindo a coluna `ambos`) para obter `pd`, `score`, `banda`, `taxa`, `parcela`, `CET` e o “ok_to_lend”.
