from bot.models.plan import Plan, PlanStatus


def format_plan_list(plans: list[Plan]) -> str:
    """Rejalar listini chiroyli formatda ko'rsatadi"""
    if not plans:
        return "📭 Bugun hech qanday reja yo'q."

    text = "📋 <b>Bugungi rejalaringiz:</b>\n\n"
    
    status_icons = {
        PlanStatus.pending: "⏳",
        PlanStatus.done: "✅",
        PlanStatus.failed: "❌"
    }

    for i, plan in enumerate(plans, 1):
        icon = status_icons.get(plan.status, "⏳")
        time_str = f"🕐 {plan.scheduled_time}" if plan.scheduled_time else "🕐 Vaqt belgilanmagan"
        text += f"{icon} <b>{i}. {plan.title}</b>\n"
        text += f"   {time_str} | ⭐ {plan.score_value} ball\n"
        if plan.description:
            text += f"   📝 {plan.description}\n"
        text += "\n"

    return text


def format_plan_confirm(plans: list[dict]) -> str:
    """GPT tahlilidan keyin tasdiqlash uchun ko'rsatadi"""
    text = "🤖 <b>Intizom AI tahlil qildi:</b>\n\n"
    
    for i, plan in enumerate(plans, 1):
        time_str = f"🕐 {plan['scheduled_time']}" if plan.get('scheduled_time') else "🕐 Vaqt yo'q"
        text += f"<b>{i}. {plan['title']}</b>\n"
        text += f"   {time_str} | ⭐ {plan.get('score_value', 5)} ball\n"
        if plan.get('description'):
            text += f"   📝 {plan['description']}\n"
        text += "\n"

    text += "✅ To'g'rimi? Tasdiqlang yoki o'zgartiring."
    return text


def format_summary(summary: dict) -> str:
    """Kunlik hisobotni formatlaydi"""
    text = "📊 <b>Bugungi hisobotingiz:</b>\n\n"
    text += f"✅ Bajarildi: <b>{len(summary['done'])} ta</b>\n"
    text += f"❌ Bajarilmadi: <b>{len(summary['failed'])} ta</b>\n"
    text += f"⏳ Kutilmoqda: <b>{len(summary['pending'])} ta</b>\n\n"
    text += f"⭐ Bugungi ball: <b>{summary['today_score']:+d}</b>\n"
    text += f"🏆 Umumiy ball: <b>{summary['total_score']}</b>\n"
    text += f"🔥 Streak: <b>{summary['streak']} kun</b>"
    return text
