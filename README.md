# ConsignP2P-QITech

Demo do projeto: https://qinvest-e6dff5bd1fe6.herokuapp.com

## 🧠 Sobre

Sistema de avaliação de **risco** e **precificação de crédito consignado** baseado em **machine learning**, desenvolvido em **Django + scikit-learn**.

---

## ⚙️ Pré-requisitos

- Python **3.13.7+**
- PostgreSQL
- Git
- VS Code (com extensões Python)
- `pip` atualizado (`pip install --upgrade pip`)

---

## 🗂️ Estrutura do Projeto

```
ConsignP2P-QITech/
├── consign_app/          # Aplicação Django principal
├── mlops/                # Componentes de machine learning
│   ├── conf/             # Configurações YAML (score, pricing)
│   └── training/         # Pipelines de treino e avaliação
├── risk/                 # Módulo de risco (endpoints e serviços)
├── outputs/              # Artefatos e relatórios gerados
├── tests/                # Testes unitários e integração
└── scripts/              # Scripts utilitários
```

---

## 🚀 Configuração Inicial

### 1. Clone e prepare o ambiente

```bash
git clone https://github.com/GuilhermePC09/ConsignP2P-QITech.git
cd ConsignP2P-QITech
```

### 2. Crie e ative o ambiente virtual

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure o arquivo `.env` na raiz do projeto

```text
DATABASE_URL=postgresql://...
SECRET_KEY=troque_isto
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

### 5. Rode as migrations e crie o superusuário

```bash
python manage.py migrate
python manage.py createsuperuser
```

## 📘 Documentação

- [README ML](ML_README.md) — detalhes dos modelos e pipelines
