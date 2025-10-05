# ConsignP2P-QITech

## Sobre
Sistema de avaliação de risco e precificação de crédito consignado baseado em machine learning.

## Pré-requisitos

- Python 3.10+
- PostgreSQL
- Git
- Poetry (recomendado)
- VS Code com extensões Python

## Estrutura do Projeto
```
ConsignP2P-QITech/
├── consign_app/          # Aplicação Django
├── mlops/                # Componentes ML
│   ├── conf/            # Configurações YAML
│   └── training/        # Pipelines de treino
├── risk/                # Módulo de risco
├── outputs/             # Artefatos gerados
├── tests/               # Testes
└── scripts/             # Scripts utilitários
```

## Configuração Inicial

1. Clone e prepare ambiente:
```bash
git clone https://github.com/seu-usuario/ConsignP2P-QITech.git
cd ConsignP2P-QITech

# Com Poetry (recomendado)
poetry install

# OU com venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Configure variáveis:
```bash
cp .env.example .env

# Edite .env com:
DATABASE_URL=postgresql://user:pass@localhost:5432/consignp2p
SECRET_KEY=sua-chave-secreta
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
PD_MODEL_PATH=mlops/training/risk__LOGR1/outputs/models/pd_logr1.joblib
SCORING_CONF=mlops/conf/scoring.yaml
PRICING_MODEL_PATH=mlops/training/pricing__LINR1/outputs/models/pricing_linr1.joblib
```

3. Prepare banco e diretórios:
```bash
createdb consignp2p
python manage.py migrate
python manage.py createsuperuser

mkdir -p outputs/{models,reports,plots}
mkdir -p mlops/training/{risk__LOGR1,pricing__LINR1}/outputs/models
```

## Desenvolvimento

1. Ative ambiente e rode servidor:
```bash
poetry shell  # ou source .venv/bin/activate
python manage.py runserver
```

2. Endpoints principais:
- Admin: http://127.0.0.1:8000/admin/
- API Docs: http://127.0.0.1:8000/api/docs/
- Score: http://127.0.0.1:8000/risk/score

3. Exemplo de request scoring:
```bash
curl -X POST http://127.0.0.1:8000/risk/score \
  -H "Content-Type: application/json" \
  -d '{
    "features": {
      "beneficio_ativo": 1,
      "tempo_beneficio_meses": 48,
      "emprego_ativo": 1,
      "tempo_emprego_meses": 36,
      "renda_media_6m": 7200.0,
      "coef_var_renda": 0.22,
      "pct_meses_saldo_neg_6m": 0.17,
      "utilizacao_cartao": 0.3,
      "pct_minimo_pago_3m": 0.28,
      "num_faturas_vencidas_3m": 1,
      "endividamento_total": 0.0,
      "parcelas_renda": 0.36,
      "DPD_max_12m": 10,
      "idade": 60,
      "tempo_rel_banco_meses": 84,
      "ambos": 1
    },
    "amount": 10000,
    "term_months": 12
  }'
```

## Testes

```bash
# Testes unitários
python manage.py test

# Teste ML
python mlops/training/risk__LOGR1/test_integration.py
```

## Documentação

- [README ML](mlops/README.md) - Detalhes dos modelos e pipelines
- [API Docs](docs/api.md) - Documentação da API

## Scripts Úteis

```bash
# Atualizar deps
poetry update  # ou pip install -r requirements.txt --upgrade

# Limpar cache
python manage.py clean_pyc
python manage.py clear_cache
```

## VS Code

Extensões recomendadas:
- Python
- Jupyter
- Git Lens
- YAML

Settings sugeridos:
```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
    "python.testing.pytestEnabled": true,
    "python.formatting.provider": "black"
}
```

## Suporte

Contato: dev@empresa.com.br