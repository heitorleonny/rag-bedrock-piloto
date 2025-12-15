import streamlit as st
from bedrock_client import chat_nova
from doc_utils import extract_text_from_pdf, extract_text_from_txt
from dynamo_utils import save_expense, totals_by_category
from finance_agent import classify_expenses, generate_spending_report
import pandas as pd
from decimal import Decimal


st.set_page_config(page_title="Agente de Finanças", layout="wide")
st.title("Agente de Finanças")
st.subheader("Coloque seus gastos")
raw = st.text_area(
    "Exemplo: 100 gasolina",
    height=160,
    placeholder="30 reais de almoço/50 uber para casa/200 mercado",
)

if st.button("Classificar"):
    if not raw.strip():
        st.warning("Cole pelo menos uma linha.")
    else:
        try:
            batch = classify_expenses(raw)
            df = pd.DataFrame([i.model_dump() for i in batch.items])
            st.success(f"Itens classificados: {len(df)}")
            st.dataframe(df, width="stretch")
            saved = []
            for item in batch.items:
                record = save_expense(item.model_dump(), batch.currency)
                saved.append(record)

        except Exception as e:
            st.error(f"Falha ao classificar: {e}")

st.subheader("📊 Totais por categoria")

if st.button("Atualizar totais"):
    totals = totals_by_category()

    if not totals:
        st.info("Nenhum gasto encontrado.")
    else:
        rows = []
        total_geral = Decimal("0")

        for cat, value in totals.items():
            rows.append({
                "Categoria": cat,
                "Total (R$)": float(value)
            })
            total_geral += value

        st.dataframe(rows, width="stretch")
        st.metric("💰 Total geral", f"R$ {float(total_geral):.2f}")

st.subheader("Relátorio de gastos")

if st.button("Gerar relatório"):
    totals = totals_by_category()
    if not totals:
        st.info("Nenhum gasto encontrado para gerar relatório.")
    else:
        with st.spinner("Gerando insights..."):
            report = generate_spending_report(totals)
        st.markdown(report)