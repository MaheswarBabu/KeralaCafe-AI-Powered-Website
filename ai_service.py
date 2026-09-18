"""
ai_service.py
-------------
The "AI Food Assistant". It always grounds itself in the *actual* menu
pulled from the database - it never invents dishes that aren't really
on the menu.

Two modes:
1. If GEMINI_API_KEY is set, it sends the real menu + the customer's
   message to Google's Gemini and asks it to reason like a real
   restaurant host: stay on-topic, substitute unavailable items with
   similar ones, and map vague cravings ("something sweet") to the
   right category - returning strict JSON.
2. Otherwise it falls back to a rule-based recommender that mimics
   the same behaviour (off-topic filtering, dish substitution, vague
   craving mapping) so the feature still works with zero configuration.
"""

import os
import json
import re
import difflib
from typing import List, Optional
from sqlalchemy.orm import Session

from models import Food

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


# =====================================================================
# Shared helpers (used by both Gemini mode and the rule-based fallback)
# =====================================================================

# Phrases that signal the message has nothing to do with food/ordering
# from this restaurant at all - e.g. "can you order me a phone".
OFF_TOPIC_KEYWORDS = [
    "phone", "mobile", "iphone", "laptop", "computer", "tablet",
    "taxi", "cab", "uber", "ola", "flight", "movie ticket", "book a hotel",
    "hotel room", "car", "bike", "scooter", "shoes", "clothes", "shirt",
    "dress", "amazon", "flipkart", "resume", "homework", "assignment",
    "weather", "news", "stock price", "bitcoin", "crypto", "recipe for",
    "how to cook", "python code", "essay",
    # Malayalam off-topic terms
    "ഫോൺ", "മൊബൈൽ", "ലാപ്‌ടോപ്പ്", "കമ്പ്യൂട്ടർ", "ടാക്സി", "കാർ", "ബൈക്ക്",
    "കാലാവസ്ഥ", "വാർത്ത", "സിനിമ", "ഹോട്ടൽ റൂം", "വസ്ത്രം", "തുണി"
]

# Specific, strong signals that the message is about our food/menu.
# Deliberately excludes generic verbs like "order", "want", "eat" since
# those show up in off-topic requests too ("order me a phone").
FOOD_SIGNAL_KEYWORDS = [
    "veg", "non-veg", "nonveg", "spicy", "mild", "dish", "menu",
    "sweet", "dessert", "starter", "main course", "beverage", "drink",
    "juice", "curry", "rice", "biryani", "biriyani", "chicken", "mutton",
    "fish", "paneer", "price", "rupee", "₹", "budget", "thali", "roll",
    "dosa", "lime", "jamun",
    # Malayalam food keywords
    "ഭക്ഷണം", "മെനു", "ബിരിയാണി", "ചിക്കൻ", "മട്ടൺ", "മീൻ", "പനീർ",
    "വെജ്", "വെജിറ്റേറിയൻ", "നോൺ-വെജ്", "എരിവ്", "മധുരം", "പായസം",
    "ജ്യൂസ്", "ദോശ", "ചോറ്", "റൈസ്", "വില", "രൂപ", "കുടിക്കാൻ", "കഴിക്കാൻ"
]

# Specific dish names people might ask for that we simply don't sell,
# mapped to the closest category we DO have so we can substitute
# gracefully instead of pretending the dish exists.
CRAVING_TO_CATEGORY = {
    "ice cream": "Desserts", "icecream": "Desserts", "cake": "Desserts",
    "pastry": "Desserts", "ഐസ്ക്രീം": "Desserts", "കേക്ക്": "Desserts",
    "pizza": "Main Course", "burger": "Main Course", "pasta": "Main Course",
    "noodles": "Main Course", "sandwich": "Main Course", "sushi": "Main Course",
    "പിസ്സ": "Main Course", "ബർഗർ": "Main Course", "നൂഡിൽസ്": "Main Course",
    "momos": "Starters", "മോമോസ്": "Starters",
    "coffee": "Beverages", "tea": "Beverages", "milkshake": "Beverages",
    "soda": "Beverages", "ചായ": "Beverages", "കാപ്പി": "Beverages",
}

# Malayalam translations for dish name matching
MALAYALAM_DISH_ALIASES = {
    "ചിക്കൻ ബിരിയാണി": "Chicken Biriyani",
    "ബിരിയാണി": "Chicken Biriyani",
    "ചിക്കൻ 65": "Chicken 65",
    "പനീർ ബട്ടർ മസാല": "Paneer Butter Masala",
    "പനീർ": "Paneer Butter Masala",
    "വെജ് ഫ്രൈഡ് റൈസ്": "Veg Fried Rice",
    "ഫ്രൈഡ് റൈസ്": "Veg Fried Rice",
    "ചില്ലി പനീർ": "Chilli Paneer",
    "ഫ്രഷ് ലൈം": "Fresh Lime",
    "നാരങ്ങ വെള്ളം": "Fresh Lime",
    "ലൈം ജ്യൂസ്": "Fresh Lime",
    "മട്ടൺ കറി": "Mutton Curry",
    "മട്ടൺ": "Mutton Curry",
    "ഗുലാബ് ജാമുൻ": "Gulab Jamun",
    "വെജ് സ്പ്രിംഗ് റോൾസ്": "Veg Spring Rolls",
    "സ്പ്രിംഗ് റോൾ": "Veg Spring Rolls",
    "മസാല ദോശ": "Masala Dosa",
    "ദോശ": "Masala Dosa",
    "ഫിഷ് ഫ്രൈ": "Fish Fry",
    "മീൻ വറുത്തത്": "Fish Fry",
    "മീൻ ഫ്രൈ": "Fish Fry",
    "തൈര് സാദം": "Curd Rice",
    "തൈര് ചോറ്": "Curd Rice",
}

CATEGORY_TRANSLATION_ML = {
    "Starters": "സ്റ്റാർട്ടറുകൾ (Starters)",
    "Main Course": "പ്രധാന വിഭവങ്ങൾ (Main Course)",
    "Desserts": "മധുര പലഹാരങ്ങൾ (Desserts)",
    "Beverages": "പാനീയങ്ങൾ (Beverages)",
}


def _is_malayalam(text: str) -> bool:
    """Detect if the message is in Malayalam script or contains prominent Malayalam keywords."""
    if re.search(r"[\u0D00-\u0D7F]", text):
        return True
    manglish_words = ["venam", "undo", "tharumo", "kazhikkan", "kudikkan", "madhuram", "eriv", "erivu", "oottu", "nalla", "enthanu", "entha"]
    text_lower = text.lower()
    return any(w in text_lower for w in manglish_words)


def _menu_as_list(db: Session) -> List[Food]:
    return db.query(Food).filter(Food.availability == True).all()  # noqa: E712


def _is_off_topic(msg: str) -> bool:
    has_off_topic = any(kw in msg for kw in OFF_TOPIC_KEYWORDS)
    has_food_signal = any(kw in msg for kw in FOOD_SIGNAL_KEYWORDS)
    return has_off_topic and not has_food_signal


def _closest_food_match(msg: str, foods: List[Food]) -> Optional[Food]:
    """If the customer named a dish that IS on our menu (even with a typo,
    a partial name, in Malayalam, or just a couple of the words in it), find it."""
    # Check Malayalam aliases first
    for ml_name, en_name in MALAYALAM_DISH_ALIASES.items():
        if ml_name in msg:
            for food in foods:
                if food.food_name.lower() == en_name.lower():
                    return food

    names = {f.food_name.lower(): f for f in foods}

    # 1. Full dish name appears in the message ("I'll take the chicken 65").
    for name, food in names.items():
        if name in msg:
            return food

    # 2. A 2-3 word phrase from the message appears inside a dish name
    words = [w for w in msg.split() if len(w) > 2]
    for size in (3, 2):
        for i in range(len(words) - size + 1):
            phrase = " ".join(words[i:i + size])
            for name, food in names.items():
                if phrase in name:
                    return food

    # 3. Fuzzy match on the whole message, then on smaller windows -
    matches = difflib.get_close_matches(msg, names.keys(), n=1, cutoff=0.72)
    if matches:
        return names[matches[0]]
    for size in (3, 2):
        for i in range(len(words) - size + 1):
            phrase = " ".join(words[i:i + size])
            close = difflib.get_close_matches(phrase, names.keys(), n=1, cutoff=0.8)
            if close:
                return names[close[0]]
    return None


def _detect_unavailable_craving(msg: str) -> Optional[str]:
    """Detect a named dish/craving that is NOT on our menu, and return
    the category we should substitute from (or None if nothing matches)."""
    for craving, category in CRAVING_TO_CATEGORY.items():
        if craving in msg:
            return category
    return None


def _parse_preferences(msg: str):
    # Check Malayalam and English veg / non-veg signals
    has_veg_word = bool(re.search(r"\bveg(etarian)?\b", msg)) or any(w in msg for w in ["വെജ്", "വെജിറ്റേറിയൻ", "സസ്യാഹാരം", "പച്ചക്കറി"])
    has_nonveg_word = (
        bool(re.search(r"non[\s-]?veg", msg))
        or bool(re.search(r"\b(chicken|mutton|fish|egg|beef|pork)\b", msg))
        or any(w in msg for w in ["നോൺ-വെജ്", "നോൺ വെജ്", "നോൺവെജ്", "മാംസാഹാരം", "ഇറച്ചി", "ചിക്കൻ", "മട്ടൺ", "മീൻ"])
    )

    wants_veg = has_veg_word and not has_nonveg_word
    wants_nonveg = has_nonveg_word

    wants_spicy = any(w in msg for w in ["spicy", "spice", "hot", "എരിവ്", "എരിവുള്ള", "സ്പൈസി"])
    wants_mild = any(w in msg for w in ["mild", "not spicy", "less spicy", "sweet", "എരിവ് കുറഞ്ഞ", "എരിവില്ലാത്ത", "മൈൽഡ്"])

    price_limit = None
    price_match = re.search(r"(?:under|below|less than|within|താഴെ|ഉള്ളിൽ)?\s*(?:rs\.?|₹|inr|രൂപ)?\s*(\d+)\s*(?:rs\.?|₹|inr|രൂപ|താഴെ)?", msg)
    if price_match and price_match.group(1):
        try:
            val = float(price_match.group(1))
            if 30 <= val <= 2000:
                price_limit = val
        except ValueError:
            pass

    category_keywords = {
        "starter": "Starters", "starters": "Starters", "സ്റ്റാർട്ടർ": "Starters", "സ്റ്റാർട്ടറുകൾ": "Starters",
        "main": "Main Course", "main course": "Main Course", "പ്രധാന ഭക്ഷണം": "Main Course",
        "dessert": "Desserts", "sweet": "Desserts", "sweets": "Desserts", "മധുര": "Desserts", "മധുരം": "Desserts", "പായസ": "Desserts", "പായസം": "Desserts", "ഡെസേർട്ട്": "Desserts",
        "drink": "Beverages", "beverage": "Beverages", "juice": "Beverages", "lime": "Beverages", "പാനീയ": "Beverages", "പാനീയം": "Beverages", "ജ്യൂസ്": "Beverages", "കുടിക്കാൻ": "Beverages", "വെള്ളം": "Beverages",
        "rice": "Main Course", "biriyani": "Main Course", "biryani": "Main Course", "ചോറ്": "Main Course", "ബിരിയാണി": "Main Course",
    }
    wanted_category = None
    for kw, cat in category_keywords.items():
        if kw in msg:
            wanted_category = cat
            break

    return {
        "wants_veg": wants_veg, "wants_nonveg": wants_nonveg,
        "wants_spicy": wants_spicy, "wants_mild": wants_mild,
        "price_limit": price_limit, "wanted_category": wanted_category,
    }


def _filter_foods(foods: List[Food], prefs: dict, category_override: Optional[str] = None):
    candidates = []
    category = category_override or prefs["wanted_category"]
    for f in foods:
        if prefs["wants_veg"] and not f.is_veg:
            continue
        if prefs["wants_nonveg"] and f.is_veg:
            continue
        if prefs["wants_spicy"] and f.spice_level < 2:
            continue
        if prefs["wants_mild"] and f.spice_level > 1:
            continue
        if prefs["price_limit"] is not None and f.price > prefs["price_limit"]:
            continue
        if category and f.category != category:
            continue
        candidates.append(f)
    return sorted(candidates, key=lambda f: -f.rating)


def _to_rec(f: Food, reason: Optional[str] = None, is_ml: bool = False):
    if not reason:
        if is_ml:
            veg_str = "വെജിറ്റേറിയൻ" if f.is_veg else "നോൺ-വെജ്"
            reason = f"{veg_str}, എരിവ് {f.spice_level}/3, റേറ്റിംഗ് {f.rating}★"
        else:
            reason = f"{'Veg' if f.is_veg else 'Non-veg'}, spice level {f.spice_level}/3, rated {f.rating}★"
    return {
        "food_id": f.food_id,
        "food_name": f.food_name,
        "price": f.price,
        "reason": reason,
    }


# =====================================================================
# Rule-based fallback (also mirrors the logic Gemini is prompted to use)
# =====================================================================

def _rule_based_recommend(message: str, foods: List[Food]):
    msg = message.lower().strip()
    is_ml = _is_malayalam(message)
    prefs = _parse_preferences(msg)

    # 1. Direct dish match
    direct_match = _closest_food_match(msg, foods)
    if direct_match:
        reason = "നിങ്ങൾ ചോദിച്ച അതേ വിഭവം!" if is_ml else "Exactly what you asked for!"
        recs = [_to_rec(direct_match, reason=reason, is_ml=is_ml)]
        similar = [
            f for f in _filter_foods(foods, prefs, category_override=direct_match.category)
            if f.food_id != direct_match.food_id
        ][:2]
        recs += [_to_rec(f, is_ml=is_ml) for f in similar]

        if is_ml:
            reply = f"നല്ല വാർത്ത! {direct_match.food_name} ഞങ്ങളുടെ മെനുവിൽ ലഭ്യമാണ്. ഇതാ വിവരങ്ങൾ:"
        else:
            reply = f"Good news - {direct_match.food_name} is on the menu! Here it is:"
        return reply, recs

    # 2. Unavailable item substitution
    substitute_category = _detect_unavailable_craving(msg)
    if substitute_category:
        candidates = _filter_foods(foods, prefs, category_override=substitute_category)[:3]
        if not candidates:
            relaxed_prefs = {**prefs, "wants_spicy": False, "wants_mild": False}
            candidates = _filter_foods(foods, relaxed_prefs, category_override=substitute_category)[:3]
        if candidates:
            if is_ml:
                cat_ml = CATEGORY_TRANSLATION_ML.get(substitute_category, substitute_category)
                reply = f"ആ വിഭവം ഇപ്പോൾ ലഭ്യമല്ല. എങ്കിലും {cat_ml} വിഭാഗത്തിൽ നിന്നുള്ള മികച്ച വിഭവങ്ങൾ ഇതാ:"
            else:
                reply = (
                    "That's not something we make here, but if you're after "
                    f"{substitute_category.lower()}, these are popular picks:"
                )
            return reply, [_to_rec(f, is_ml=is_ml) for f in candidates]

    # 3. Off-topic check
    if _is_off_topic(msg):
        if is_ml:
            return (
                "ഞാൻ ഭക്ഷണ മെനുവിനെക്കുറിച്ചുള്ള വിവരങ്ങൾ മാത്രമേ നൽകുകയുള്ളൂ. "
                "നിങ്ങൾക്ക് എന്താണ് കഴിക്കാൻ താല്പര്യം എന്ന് പറയൂ, ഞാൻ സഹായിക്കാം!",
                [],
            )
        return (
            "I can only help with our food menu - reservations, dishes, and orders. "
            "Let me know what you're craving and I'll find something for you!",
            [],
        )

    # 4. Standard preference-based filtering
    candidates = _filter_foods(foods, prefs)
    if not candidates:
        candidates = sorted(foods, key=lambda f: -f.rating)[:3]
    else:
        candidates = candidates[:5]

    if is_ml:
        ml_bits = []
        if prefs["wants_veg"]:
            ml_bits.append("വെജിറ്റേറിയൻ")
        if prefs["wants_nonveg"]:
            ml_bits.append("നോൺ-വെജ്")
        if prefs["wants_spicy"]:
            ml_bits.append("എരിവുള്ള")
        if prefs["wants_mild"]:
            ml_bits.append("എരിവ് കുറഞ്ഞ")
        if prefs["price_limit"]:
            ml_bits.append(f"₹{int(prefs['price_limit'])} രൂപയിൽ താഴെയുള്ള")
        if prefs["wanted_category"]:
            ml_bits.append(CATEGORY_TRANSLATION_ML.get(prefs["wanted_category"], prefs["wanted_category"]))

        if ml_bits:
            reply = f"നിങ്ങൾ ആവശ്യപ്പെട്ട {', '.join(ml_bits)} വിഭവങ്ങൾ ഞങ്ങളുടെ മെനുവിൽ നിന്ന് ഇതാ:"
        else:
            reply = "ഞങ്ങളുടെ മെനുവിൽ നിന്നുള്ള ചില മികച്ച വിഭവങ്ങൾ ഇതാ:"
    else:
        reply_bits = []
        if prefs["wants_veg"]:
            reply_bits.append("vegetarian")
        if prefs["wants_nonveg"]:
            reply_bits.append("non-vegetarian")
        if prefs["wants_spicy"]:
            reply_bits.append("spicy")
        if prefs["wants_mild"]:
            reply_bits.append("mild")
        if prefs["price_limit"]:
            reply_bits.append(f"under ₹{int(prefs['price_limit'])}")
        if prefs["wanted_category"]:
            reply_bits.append(prefs["wanted_category"].lower())

        if reply_bits:
            reply = f"Based on your preference for {', '.join(reply_bits)}, here's what I'd suggest from our menu:"
        else:
            reply = "Here are a few dishes from our menu you might enjoy:"

    return reply, [_to_rec(f, is_ml=is_ml) for f in candidates]


# =====================================================================
# Gemini-powered mode
# =====================================================================

def _gemini_recommend(message: str, foods: List[Food]):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)

    menu_payload = [
        {
            "food_id": f.food_id,
            "food_name": f.food_name,
            "category": f.category,
            "price": f.price,
            "is_veg": f.is_veg,
            "spice_level": f.spice_level,
            "rating": f.rating,
            "description": f.description,
        }
        for f in foods
    ]

    system_prompt = f"""You are CafeMate, Kerala Cafe's friendly restaurant food assistant - a welcoming host
taking food requests for Kerala Cafe. You must recommend dishes ONLY
from the JSON menu list below. Never invent a dish that isn't in the list.

Follow these rules carefully:

1. STAY ON TOPIC. If the customer's message has nothing to do with our food
   menu, reservations, or ordering (e.g. they ask you to order a phone, book
   a flight, or chat about something unrelated), do NOT recommend any dishes.
   Set "off_topic" to true, leave "recommendations" empty, and politely say
   in "reply" that you can only help with the food menu.

2. SUBSTITUTE UNAVAILABLE ITEMS GRACEFULLY. If the customer names a specific
   dish that is NOT in the menu list (e.g. "veg biryani" when we have no veg
   biryani, or "ice cream", "pizza", "burger" which we simply don't serve),
   do not pretend it exists. Say it's not on our menu right now, then
   recommend 2-3 of the closest real alternatives (similar category, similar
   veg/non-veg and spice profile) with a short reason each dish is a good
   substitute.

3. MAP VAGUE CRAVINGS TO CATEGORIES. If the customer asks generally for
   "something sweet", "a dessert", "a starter", "a drink", etc. without
   naming a specific dish, pick the best-rated items from that category.

4. If the requested dish IS actually on the menu, confirm it enthusiastically
   and recommend it (plus 1-2 similar dishes if useful).

5. Respect stated preferences: vegetarian/non-vegetarian, spice level, and
   budget (price ceiling), whenever they're mentioned.

6. MULTILINGUAL SUPPORT (MALAYALAM / ENGLISH):
   If the customer speaks, types, or asks in Malayalam (മലയാളം script or Manglish),
   understand their request, match with our menu items, and write the "reply"
   and each recommendation's "reason" in natural, friendly Malayalam (keeping the food_name
   as written in the menu so it matches the order system).

Respond with STRICT JSON ONLY (no markdown, no code fences, no commentary)
in exactly this shape:
{{"off_topic": <true|false>, "reply": "<one short friendly sentence>",
"recommendations": [{{"food_id": <int>, "food_name": "<string>",
"price": <number>, "reason": "<short reason>"}}]}}

MENU:
{json.dumps(menu_payload)}"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=message,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            max_output_tokens=700,
        ),
    )

    text = (response.text or "").strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    data = json.loads(text)
    return data.get("reply", ""), data.get("recommendations", []), data.get("off_topic", False)


def get_recommendation(db: Session, message: str):
    foods = _menu_as_list(db)

    if GEMINI_API_KEY:
        try:
            reply, recs, off_topic = _gemini_recommend(message, foods)
            if off_topic:
                return reply, []
            # Guard: drop any food_id Gemini may have hallucinated
            valid_ids = {f.food_id for f in foods}
            recs = [r for r in recs if r.get("food_id") in valid_ids]
            if reply:
                return reply, recs
        except Exception:
            # Any API/parse issue -> silently fall back so the feature never breaks
            pass

    return _rule_based_recommend(message, foods)

