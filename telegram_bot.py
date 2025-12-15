from datetime import datetime, timezone
import os
import re
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from finance_agent import chat_with_finance_context, classify_expenses, generate_spending_report, answer_finance_question
from dynamo_utils import save_expense, top_n_expenses, totals_by_category, list_expenses_month, total_amount, get_monthly_income, totals_by_category_items

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


CHAT_MEMORY = {}
MAX_TURNS = 8

def mem_add(chat_id: int, role: str, content: str):
    hist = CHAT_MEMORY.get(chat_id, [])
    hist.append({"role": role, "content": content})
    CHAT_MEMORY[chat_id] = hist[-MAX_TURNS:]

def mem_get(chat_id: int):
    return CHAT_MEMORY.get(chat_id, [])

HELP_TEXT = (
    "Comandos:\n"
    "/start - boas-vindas\n"
    "/help - ajuda\n"
    "/report - relatório (totais + insight)\n\n"
    "Envie gastos (um por linha), ex:\n"
    "100 gasolina\n50 jantar\n200 mouse\n20 passagem"
)

def looks_like_expenses(text: str) -> bool:
    # heurística simples: linha começando com número (50, 50.90, 50,90)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return False
    return any(re.match(r"^\d+([.,]\d{1,2})?\s+\S+", l) for l in lines)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot de Finanças ativo!\n\n" + HELP_TEXT)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT)

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    totals = totals_by_category()
    if not totals:
        await update.message.reply_text("Ainda não há gastos salvos.")
        return

    # resumo numérico
    lines = ["📊 Totais por categoria:"]
    for cat, val in totals.items():
        lines.append(f"- {cat}: R$ {float(val):.2f}")

    # insight com LLM
    insight = generate_spending_report(totals)

    await update.message.reply_text("\n".join(lines))
    await update.message.reply_text("🧠 Insight:\n" + insight)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_id = update.effective_chat.id

    # 1) Se NÃO parece gasto, tratar como PERGUNTA (aqui entra o bloco que você perguntou)
    if not looks_like_expenses(text):
        mem_add(chat_id, "user", text)

        now = datetime.now(timezone.utc)
        items = list_expenses_month(now.year, now.month)

        if not items:
            await update.message.reply_text(
                "Ainda não tenho gastos salvos deste mês. Envie alguns gastos (valor descrição) e tente de novo."
            )
            return

        totals = totals_by_category_items(items)
        total_spent = total_amount(items)
        income = get_monthly_income()
        month_label = now.strftime("%Y-%m")
        top5 = top_n_expenses(items, n=5)

        await update.message.reply_text("🧠 Pensando com base nos seus gastos do mês...")
        answer = chat_with_finance_context(
            user_message=text,
            memory=mem_get(chat_id),
            income=income,
            month_label=month_label,
            totals=totals,
            total_spent=total_spent,
            top_expenses=top5
        )

        mem_add(chat_id, "assistant", answer)
        await update.message.reply_text(answer)
        return

    # 2) Caso pareça gasto: classificar e salvar (fluxo que você já tinha)
    try:
        batch = classify_expenses(text)

        saved = 0
        reply_lines = [f"✅ Salvei {len(batch.items)} gasto(s):"]
        for item in batch.items:
            save_expense(item.model_dump(), batch.currency)
            saved += 1
            reply_lines.append(
                f"- R$ {item.amount:.2f} | {item.description_normalized} | {item.category} ({item.confidence:.2f})"
            )

        reply = "\n".join(reply_lines)
        mem_add(chat_id, "user", text)
        mem_add(chat_id, "assistant", reply)

        await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text(f"❌ Falha ao processar: {e}")





def main():
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN não definido no .env")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Bot rodando (polling)... Ctrl+C para parar.")
    app.run_polling()

if __name__ == "__main__":
    main()
