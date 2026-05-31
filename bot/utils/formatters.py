from bot.models.plan import Plan, PlanStatus


def format_plan_list(plans: list[Plan]) -> str:
    """Rejalar ro'yxatini premium ko'rinishda chiqaradi"""
    if not plans:
        return "📭 Bugun hali reja yo'q.\n\n<i>Ovoz yoki matn bilan rejangizni ayting 👇</i>"

    status_icons = {
        PlanStatus.pending: "⬜️",
        PlanStatus.done: "✅",
        PlanStatus.failed: "❌",
    }

    text = "📋 <b>Bugungi rejalaring</b>\n━━━━━━━━━━━━━\n\n"
    for plan in plans:
        icon = status_icons.get(plan.status, "⬜️")
        time_str = f"🕐 {plan.scheduled_time}" if plan.scheduled_time else "🕐 Vaqtsiz"
        text += f"{icon} <b>{plan.title}</b>\n"
        text += f"     {time_str}   ·   ⚡️ +{plan.score_value} XP\n"
        if plan.description:
            text += f"     📝 <i>{plan.description}</i>\n"
        text += "\n"

    return text


def format_plan_confirm(plans: list[dict]) -> str:
    """GPT tahlilidan keyin tasdiqlash uchun premium ko'rinish"""
    text = "🤖 <b>Intizom AI rejangni tayyorladi:</b>\n━━━━━━━━━━━━━\n\n"

    for i, plan in enumerate(plans, 1):
        time_str = f"🕐 {plan['scheduled_time']}" if plan.get('scheduled_time') else "🕐 Vaqtsiz"
        text += f"<b>{i}. {plan['title']}</b>\n"
        text += f"     {time_str}   ·   ⚡️ +{plan.get('score_value', 5)} XP\n"
        if plan.get('description'):
            text += f"     📝 <i>{plan['description']}</i>\n"
        text += "\n"

    text += "✨ To'g'rimi? Tasdiqlang yoki qaytadan yozing."
    return text


def format_summary(summary: dict) -> str:
    """Kunlik hisobotni formatlaydi"""
    text = "🌙 <b>Kun yakuni</b>\n━━━━━━━━━━━━━\n\n"
    text += f"✅ Bajarildi: <b>{len(summary['done'])} ta</b>\n"
    text += f"❌ Bajarilmadi: <b>{len(summary['failed'])} ta</b>\n"
    text += f"⏳ Qoldi: <b>{len(summary['pending'])} ta</b>\n\n"
    text += f"⚡️ Bugungi XP: <b>{summary['today_score']:+d}</b>\n"
    text += f"🏆 Umumiy ball: <b>{summary['total_score']}</b>\n"
    text += f"🔥 Streak: <b>{summary['streak']} kun</b>"
    return text
