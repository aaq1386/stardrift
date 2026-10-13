"""Permanent upgrades and cosmetic purchases for STARDRIFT."""

import json
from database import Database


UPGRADES = {
    "paddle_width": {
        "name": "Extended Paddle",
        "description": "+8% base paddle width per level",
        "prices": [150, 300, 550, 900, 1400],
        "max_level": 5,
        "category": "mobility",
        "requires": {},
    },
    "paddle_speed": {
        "name": "Kinetic Drive",
        "description": "+7% paddle movement speed per level",
        "prices": [120, 250, 450, 750, 1200],
        "max_level": 5,
        "category": "mobility",
        "requires": {},
    },
    "laser": {
        "name": "Twin Laser",
        "description": "Unlock twin lasers; activate with Ctrl",
        "prices": [350, 600, 950, 1400, 2000],
        "max_level": 5,
        "category": "offense",
        "requires": {"paddle_speed": 1},
    },
    "permanent_shield": {
        "name": "Emergency Barrier",
        "description": "Unlock a temporary defensive barrier; activate with Shift",
        "prices": [300, 550, 900, 1400],
        "max_level": 4,
        "category": "defense",
        "requires": {"paddle_width": 1},
    },
    "emergency_bomb": {
        "name": "Emergency Bomb",
        "description": "Destroy 5 random bricks during a run",
        "prices": [300],
        "max_level": 1,
        "category": "offense",
        "requires": {"laser": 1},
    },
    "row_clear": {
        "name": "Row Clear",
        "description": "Clear the lowest brick row; press R (180 CR/use)",
        "prices": [450],
        "max_level": 1,
        "category": "offense",
        "requires": {"laser": 2},
    },
    "extra_life": {
        "name": "Extra Starting Life",
        "description": "+1 starting life per level; maximum 5 starting lives",
        "prices": [700, 1200],
        "max_level": 2,
        "category": "defense",
        "requires": {"permanent_shield": 1},
    },
}


# === Permanent ball color cosmetics ===
BALL_COLORS = {
    "ball_color_cyan": {
        "name": "Cyan",
        "color": (0, 235, 255),
        "price": 0,
        "description": "Classic energy blue",
    },
    "ball_color_crimson": {
        "name": "Crimson",
        "color": (255, 65, 85),
        "price": 10,
        "description": "Crimson red energy",
    },
    "ball_color_emerald": {
        "name": "Emerald",
        "color": (50, 230, 135),
        "price": 10,
        "description": "Emerald green energy",
    },
    "ball_color_violet": {
        "name": "Violet",
        "color": (175, 95, 255),
        "price": 10,
        "description": "Violet plasma energy",
    },
    "ball_color_amber": {
        "name": "Amber",
        "color": (255, 180, 45),
        "price": 10,
        "description": "Amber gold energy",
    },
    "ball_color_ice": {
        "name": "Ice",
        "color": (220, 245, 255),
        "price": 10,
        "description": "Icy white-blue energy",
    },
    "ball_skin_iran": {
        "name": "Iran Flag",
        "color": (235, 45, 55),
        "price": 100,
        "description": "Iranian tricolor with the central emblem",
    },
}


class Shop:
    def __init__(self, database=None):
        self.db = database or Database()

    # === Ball color persistence ===
    def get_owned_ball_colors(self):
        raw = self.db.get_setting("ball_colors_owned", '["ball_color_cyan"]')
        try:
            saved = json.loads(raw)
        except (TypeError, ValueError):
            saved = ["ball_color_cyan"]

        if not isinstance(saved, list):
            saved = ["ball_color_cyan"]

        # Ignore invalid keys and always preserve the free default color.
        owned = {
            key for key in saved
            if isinstance(key, str) and key in BALL_COLORS
        }
        owned.add("ball_color_cyan")
        return owned

    def get_active_ball_color_key(self):
        key = self.db.get_setting("ball_color_active", "ball_color_cyan")
        if key not in self.get_owned_ball_colors():
            key = "ball_color_cyan"
            self.db.set_setting("ball_color_active", key)
        return key

    def get_active_ball_color(self):
        key = self.get_active_ball_color_key()
        return BALL_COLORS[key]["color"]

    @staticmethod
    def _missing_requirements(upgrade_key, levels):
        """Return prerequisites that have not been met."""
        config = UPGRADES[upgrade_key]
        missing = []

        for required_key, required_level in config["requires"].items():
            current_level = levels.get(required_key, 0)

            if current_level < required_level:
                required_name = UPGRADES[required_key]["name"]
                missing.append({
                    "key": required_key,
                    "name": required_name,
                    "required_level": required_level,
                    "current_level": current_level,
                })

        return missing

    def get_items(self):
        """Return shop items with prices, levels, and purchase status."""
        profile = self.db.get_profile()
        levels = self.db.get_upgrades()
        credits = profile["credits"]
        items = []

        for key, config in UPGRADES.items():
            level = levels.get(key, 0)
            max_level = config["max_level"]
            maxed = level >= max_level

            price = (
                config["prices"][level]
                if not maxed and level < len(config["prices"])
                else None
            )

            missing = self._missing_requirements(key, levels)

            if maxed:
                status = "unlocked" if key in ("emergency_bomb", "row_clear") else "maxed"
            elif missing:
                status = "locked"
            elif credits < price:
                status = "insufficient_credits"
            else:
                status = "available"

            items.append({
                "key": key,
                "name": config["name"],
                "description": config["description"],
                "category": config["category"],
                "level": level,
                "max_level": max_level,
                "price": price,
                "credits": credits,
                "maxed": maxed,
                "affordable": price is not None and credits >= price,
                "locked": bool(missing),
                "missing_requirements": missing,
                "status": status,
            })

        # === Cosmetic color cards ===
        owned_colors = self.get_owned_ball_colors()
        active_color = self.get_active_ball_color_key()

        for key, config in BALL_COLORS.items():
            owned = key in owned_colors
            equipped = key == active_color
            price = config["price"]

            if equipped:
                status = "equipped"
            elif owned:
                status = "owned"
            elif credits < price:
                status = "insufficient_credits"
            else:
                status = "available"

            items.append({
                "key": key,
                "name": config["name"],
                "description": config["description"],
                "category": "cosmetic",
                "level": 1 if owned else 0,
                "max_level": 1,
                "price": price,
                "credits": credits,
                "maxed": owned,
                "affordable": owned or credits >= price,
                "locked": False,
                "missing_requirements": [],
                "status": status,
                "color": config["color"],
            })

        return items

    def purchase(self, upgrade_key):
        """Purchase an upgrade or permanently unlock/equip a ball color."""
        if upgrade_key in BALL_COLORS:
            config = BALL_COLORS[upgrade_key]
            owned = self.get_owned_ball_colors()

            if upgrade_key in owned:
                self.db.set_setting("ball_color_active", upgrade_key)
                return True, f"{config['name']} ball color equipped."

            price = config["price"]
            if not self.db.spend_credits(price, f"unlock_{upgrade_key}"):
                return False, "Not enough credits."

            owned.add(upgrade_key)
            self.db.set_setting(
                "ball_colors_owned",
                json.dumps(sorted(owned), separators=(",", ":")),
            )
            self.db.set_setting("ball_color_active", upgrade_key)
            return True, f"{config['name']} ball color purchased and equipped."

        config = UPGRADES.get(upgrade_key)

        if config is None:
            return False, "Unknown upgrade."

        levels = self.db.get_upgrades()
        current_level = levels.get(upgrade_key, 0)

        if current_level >= config["max_level"]:
            return False, "Maximum level reached."

        missing = self._missing_requirements(upgrade_key, levels)

        if missing:
            requirement = missing[0]
            return False, (
                f"Locked: {requirement['name']} "
                f"level {requirement['required_level']} is required."
            )

        if current_level >= len(config["prices"]):
            return False, "No further upgrades available."

        price = config["prices"][current_level]

        success, result = self.db.purchase_upgrade(
            upgrade_key=upgrade_key,
            expected_level=current_level,
            price=price,
            max_level=config["max_level"],
        )

        if not success:
            messages = {
                "insufficient_credits": "Not enough credits.",
                "max_level": "Maximum level reached.",
                "level_changed": "Upgrade changed. Please try again.",
                "invalid_purchase": "Invalid purchase.",
            }
            return False, messages.get(result, "Purchase failed.")

        if upgrade_key == "emergency_bomb":
            return True, "Emergency Bomb unlocked! Use B during a run."
        if upgrade_key == "row_clear":
            return True, "Row Clear unlocked! Use R during a run."
        return True, f"{config['name']} upgraded to level {result}."
