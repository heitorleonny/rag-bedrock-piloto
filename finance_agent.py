import json
import re
from pydantic import BaseModel, Field, AliasChoices
from typing import List, Literal
from bedrock_client import chat_nova
from decimal import Decimal

Category = Literal[
    "Alimentação", "Transporte", "Moradia", "Contas/Serviços", "Saúde",
    "Educação", "Lazer", "Compras", "Tecnologia", "Assinaturas", "Outros"
]


class ExpenseItem(BaseModel):
    amount: float = Field(..., description="Valor da despesa em reais")
    description_raw: str = Field(
        ...,
        validation_alias=AliasChoices("description_raw", "description")
    )
    description_normalized: str
    category: Category
    confidence: float = Field(..., ge=0.0, le=1.0)

class ExpenseBatch(BaseModel):
    currency: str = "BRL"
    items: List[ExpenseItem]

def _extract_json(text: str) -> str:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("Modelo não retornou JSON válido.")
    return m.group(0)

def classify_expenses(multiline_text: str) -> ExpenseBatch:
    prompt = f"""
    Você é um assistente financeiro. Receba uma lista de gastos (uma linha por gasto).
    Cada linha normalmente tem: <valor> <descrição>.
    Converta isso para JSON estrito no formato:

    {{
    "currency": "BRL",
    "items": [
        {{
        "amount": 100.0,
        "description_raw": "100 gasolino",
        "description_normalized": "gasolina",
        "category": "Transporte",
        "confidence": 0.90
        }}
    ]
    }}

    Regras:
    - Se a linha estiver ambígua, categorize como "Outros" e reduza confidence.
    - Corrija erros comuns de digitação (ex.: "gasolino" -> "gasolina").
    - Não invente itens que não existem.
    - Retorne APENAS JSON. Sem comentários.

    Categorias permitidas:
    Alimentação, Transporte, Moradia, Contas/Serviços, Saúde, Educação,
    Lazer, Compras, Tecnologia, Assinaturas, Outros

    Entrada:
    {multiline_text}
    """.strip()

    resp = chat_nova([{"role": "user", "content": prompt}], max_tokens=800, temperature=0.1)
    raw_json = _extract_json(resp)
    print(resp)
    data = json.loads(raw_json)
    return ExpenseBatch(**data)


def generate_spending_report(totals: dict, currency: str = "BRL") -> str:
    """
    totals: dict with category (str) as keys and Decimal as values
    """

    totals_simple = {k: float(v) for k, v in totals.items()}

    prompt = f"""
Você é um assistente financeiro pessoal. Gere um relatório curto, claro e útil
com base nos totais por categoria abaixo.

Regras:
- Responda em português do Brasil.
- Use bullets e números quando fizer sentido.
- Não invente gastos; use apenas os dados fornecidos.
- Seja prático: 1 sugestão concreta no final.
- Formato: título + 4 a 8 linhas no máximo.

Moeda: {currency}
Totais por categoria (valores numéricos):
{totals_simple}
""".strip()

    resp = chat_nova(
        [{"role": "user", "content": prompt}],
        max_tokens=400,
        temperature=0.3,
        top_p=0.9,
    )
    return resp

def answer_finance_question(question: str, income: Decimal, month_label: str, totals: dict, total_spent: Decimal) -> str:
    totals_simple = {k: float(v) for k, v in totals.items()}

    prompt = f"""
Você é um mentor financeiro pessoal. Responda a pergunta do usuário usando os dados abaixo.
Seja prático, com passos e contas simples. Não invente dados.

Contexto:
- Renda mensal: R$ {float(income):.2f}
- Mês: {month_label}
- Total gasto no mês: R$ {float(total_spent):.2f}
- Totais por categoria: {totals_simple}

Pergunta do usuário:
{question}

Formato da resposta (IMPORTANTE):
- NÃO use Markdown com ### ou ####
- NÃO use tabelas
- Use emojis como separadores
- Use frases curtas
- Use listas com hífen (-)
- Quebre a resposta em blocos visuais

Modelo visual esperado:

📊 SITUAÇÃO ATUAL
Renda: R$ X
Gasto no mês: R$ Y
Saldo: R$ Z

⚠️ DIAGNÓSTICO
1 a 2 frases objetivas.

🧭 ESTRATÉGIAS
1️⃣ Conservadora
- Aluguel recomendado: R$ X
- Impacto: X

2️⃣ Moderada
- Aluguel recomendado: R$ X
- Impacto: X

3️⃣ Agressiva
- Aluguel recomendado: R$ X
- Impacto: X

✅ PRÓXIMA SEMANA
- [ ] ação 1
- [ ] ação 2
- [ ] ação 3
""".strip()

    return chat_nova(
        [{"role": "user", "content": prompt}],
        max_tokens=650,
        temperature=0.3,
        top_p=0.9,
    )

def chat_with_finance_context(
    user_message: str,
    memory: list,
    income: Decimal,
    month_label: str,
    totals: dict,
    total_spent: Decimal,
    top_expenses: list | None = None,
) -> str:
    totals_simple = {k: float(v) for k, v in totals.items()}
    top_expenses = top_expenses or []

    system = f"""
Você é um assistente financeiro pessoal em formato de conversa (tipo WhatsApp).
Tom: humano, direto, acolhedor e prático. Nada de relatório.

Regras de estilo:
- Sem Markdown (não use **, ###, etc.)
- Respostas curtas: 3 a 7 linhas.
- Primeiro responda a pergunta. Depois faça 1 pergunta curta para continuar.
- Não liste “opções 1/2/3” a menos que o usuário peça.
- Use no máximo 1 número por linha (evita “enchente” de valores).
- Se notar algo fora do normal, comente com delicadeza (sem julgamento).

Dados do mês {month_label}:
Renda: R$ {float(income):.2f}
Total gasto: R$ {float(total_spent):.2f}
Totais por categoria: { {k: float(v) for k,v in totals.items()} }
Top gastos: {top_expenses}
""".strip()

    messages = [{"role": "user", "content": system}]
    # injeta memória curta (histórico)
    for m in memory:
        messages.append(m)
    messages.append({"role": "user", "content": user_message})

    return chat_nova(messages, max_tokens=650, temperature=0.35, top_p=0.9)